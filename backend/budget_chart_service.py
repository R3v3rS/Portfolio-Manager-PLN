"""Daily shopping pace and total spending, with timing-neutral fixed payments."""
import calendar
from collections import defaultdict
from datetime import date


def comparison_date(due,paid=None):
    # Early payment advances the allowance; late payment never postpones it.
    return min(due,paid) if paid else due


def nominal_bill(bill):
    return round(bill.get('planned_amount',bill.get('base_amount',bill['amount']))*100)


def daily_month_plan(categories,bills,loans,reserves,apply_exclusions=False):
    """Keep the fixed planned amount independent of its eventual payment."""
    from budget_category_hierarchy_service import plan_amounts
    fixed,gross,coverage=defaultdict(int),defaultdict(int),defaultdict(int)
    media={r['reserve_id']:r for r in reserves if r.get('monthly_amount') is not None and not r.get('open_ended')}
    managed={r['category_id'] for r in media.values()}
    manual={c['id']:round(c['manual_plan']*100) for c in categories if c['id'] not in managed}
    for bill in bills:
        if bill.get('reserve_id') in media:continue
        amount=nominal_bill(bill)
        cover=min(amount,round(bill.get('reserve_covered',0)*100))
        category=bill['category_id']
        gross[category]+=amount;coverage[category]+=cover;fixed[category]+=amount-cover
    for reserve in media.values():
        amount=round(reserve['planned']*100)
        gross[reserve['category_id']]+=amount;fixed[reserve['category_id']]+=amount
    for loan in loans:
        if loan['category_id'] is not None:
            amount=round(loan['amount']*100)
            gross[loan['category_id']]+=amount;fixed[loan['category_id']]+=amount
    planned=plan_amounts(categories,manual,gross)
    result=0
    for root in (c for c in categories if not c['parent_id']):
        if apply_exclusions and root.get('daily_pace_included') is False:
            continue
        ids={root['id'],*[c['id'] for c in categories if c['parent_id']==root['id']]}
        own_plan=planned[root['id']]+round(root.get('carryover',0)*100)-sum(coverage[i] for i in ids)
        excluded_plan=sum(max(0,manual.get(c['id'],0)-gross[c['id']]) for c in categories if c['parent_id']==root['id'] and c.get('daily_pace_included') is False) if apply_exclusions else 0
        result+=max(0,own_plan-sum(fixed[i] for i in ids)-excluded_plan)
    return result


def daily_ledger(db,month,media_categories):
    """Refunds follow the original purchase; fixed payments are not shopping."""
    excluded={r[0] for r in db.execute('''SELECT entry_id FROM budget_bill_payments_v2
        UNION SELECT budget_entry_id FROM loan_installment_payments
        UNION SELECT budget_entry_id FROM loan_overpayments
        UNION SELECT budget_entry_id FROM budget_reserve_movements WHERE kind='SPEND' ''') if r[0] is not None}
    result=defaultdict(int)
    for entry in db.execute('''SELECT e.*,rf.purchase_entry_id FROM budget_entries_v2 e
        LEFT JOIN budget_purchase_refunds rf ON rf.entry_id=e.id WHERE substr(e.date,1,7)=?''',(month,)):
        if entry['kind']!='EXPENSE' and not entry['purchase_entry_id']:continue
        if (entry['purchase_entry_id'] or entry['id']) in excluded:continue
        media=sum(r['amount_cents'] for r in db.execute('SELECT category_id,amount_cents FROM budget_entry_lines_v2 WHERE entry_id=?',(entry['id'],)) if r['category_id'] in media_categories)
        result[entry['date']]+=(entry['amount_cents']-media)*(-1 if entry['purchase_entry_id'] else 1)
    return result


def fixed_summary(bills,loans):
    planned=paid=pending=overruns=early=paid_count=0
    for bill in bills:
        amount=nominal_bill(bill);planned+=amount
        if bill['status']=='PAID':
            actual=round(bill['amount']*100);paid+=actual;paid_count+=1
            overruns+=max(0,actual-amount)
            early+=int(bool(bill.get('paid_on') and bill['paid_on']<bill['due_date']))
        else:pending+=amount
    for loan in loans:
        amount=round(loan['amount']*100);planned+=amount
        if loan['paid']:
            actual=round((loan.get('paid_amount') if loan.get('paid_amount') is not None else loan['amount'])*100)
            paid+=actual;paid_count+=1;overruns+=max(0,actual-amount)
            early+=int(bool(loan.get('paid_on') and loan['paid_on']<loan['date']))
        else:pending+=amount
    return dict(planned=planned/100,paid=paid/100,pending=pending/100,over_plan=overruns/100,
                early_count=early,paid_count=paid_count,count=len(bills)+len(loans))


def pace(db,month,categories,bills,loans,reserves,totals):
    from budget_summary_service import reserve_budget_costs
    from budget_refunds_service import flows
    days=calendar.monthrange(*map(int,month.split('-')))[1]
    full_daily_plan=daily_month_plan(categories,bills,loans,reserves)
    daily_plan=daily_month_plan(categories,bills,loans,reserves,apply_exclusions=True)
    media=[r for r in reserves if r.get('monthly_amount') is not None and not r.get('open_ended')]
    media_ids={r['reserve_id'] for r in media}
    excluded_categories={c['id'] for c in categories if c.get('daily_pace_effective') is False}
    daily_changes=daily_ledger(db,month,{r['category_id'] for r in media}|excluded_categories)
    cash_fixed=[];budget_fixed=[]
    for bill in bills:
        amount=nominal_bill(bill)
        timing=comparison_date(bill['due_date'],bill.get('paid_on'))
        cash_fixed.append((timing,amount))
        if bill.get('reserve_id') not in media_ids:
            budget_fixed.append((timing,max(0,amount-round(bill.get('reserve_covered',0)*100))))
    for loan in loans:
        timing=comparison_date(loan['date'],loan.get('paid_on'))
        amount=round(loan['amount']*100)
        cash_fixed.append((timing,amount));budget_fixed.append((timing,amount))
    allocations=round((totals['reserve_plan_extra']+sum(r['contributed'] for r in reserves if r.get('monthly_amount') is None or r.get('open_ended')))*100)
    media_plan=sum(round(r['planned']*100) for r in media)
    result=[];daily_spent=0
    for number in range(1,days+1):
        day=f'{month}-{number:02d}'
        spent=flows(db,month+'-01',day)[1]/100
        adjustment=reserve_budget_costs(db,month+'-01',day)['reserve_adjustment']
        daily_spent+=daily_changes[day]
        visible=day<=date.today().isoformat()
        result.append(dict(date=day,cash_spent=spent if visible else None,budget_spent=round(spent+adjustment,2) if visible else None,
            daily_spent=daily_spent/100 if visible else None,daily_plan=round(daily_plan*number/days)/100,
            cash_plan=round(full_daily_plan*number/days+sum(a for d,a in cash_fixed if d<=day))/100,
            budget_plan=round((full_daily_plan+allocations+media_plan)*number/days+sum(a for d,a in budget_fixed if d<=day))/100))
    return result

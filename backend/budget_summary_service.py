"""Shared definitions for actual balances, monthly spending and unplanned funds."""

import calendar
from datetime import date
from budget_category_hierarchy_service import category_workspace


def reserve_budget_costs(db, first, end):
    row = db.execute('''SELECT COALESCE(SUM(budget_cost_cents),0),
        COALESCE(SUM(CASE WHEN kind='ADD' THEN budget_cost_cents ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='RELEASE' THEN -budget_cost_cents ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='SPEND' THEN -budget_cost_cents ELSE 0 END),0)
        FROM budget_reserve_movements WHERE date BETWEEN ? AND ?''', (first,end)).fetchone()
    return dict(reserve_adjustment=row[0]/100,reserve_contributions=row[1]/100,
                reserve_released=row[2]/100,reserve_settled=row[3]/100)


def period_spending(db, month, today=None):
    """Recorded expenses through today, without future entries or own transfers."""
    today = today or date.today()
    first = month + '-01'
    month_end = f"{month}-{calendar.monthrange(*map(int, month.split('-')))[1]:02d}"
    through = min(today.isoformat(), month_end)
    flows = db.execute('''SELECT COALESCE(SUM(amount_cents),0), COUNT(*)
        FROM budget_entries_v2 WHERE kind='EXPENSE' AND date BETWEEN ? AND ?''',
        (first, through)).fetchone()
    allocation = reserve_budget_costs(db, first, through)
    spent = flows[0] / 100
    from budget_refunds_service import flows as net_flows
    net=net_flows(db,first,through)
    spent=net[1]/100
    return {
        'first': first, 'through': through if through >= first else None,
        'spent': spent, 'refunds': net[2]/100, 'expense_count': flows[1], **allocation,
        'budget_spent': round(spent + allocation['reserve_adjustment'], 2),
    }


def month_income_cost(db,month,spent):
    """Costs financed this month; releasing old savings is not monthly income."""
    rows=db.execute('''SELECT m.reserve_id,
        SUM(CASE WHEN m.kind='ADD' THEN m.budget_cost_cents ELSE 0 END) contributed,
        SUM(CASE WHEN m.kind='RELEASE' THEN -m.budget_cost_cents
            WHEN m.kind='SPEND' THEN MAX(0,-m.budget_cost_cents-COALESCE(e.amount_cents,0)) ELSE 0 END) released,
        SUM(CASE WHEN m.kind='SPEND' THEN MIN(-m.budget_cost_cents,COALESCE(e.amount_cents,0)) ELSE 0 END) settled
        FROM budget_reserve_movements m LEFT JOIN budget_entries_v2 e ON e.id=m.budget_entry_id
        WHERE substr(m.date,1,7)=? GROUP BY m.reserve_id''',(month,)).fetchall()
    newly_allocated=sum(max(0,r['contributed']-r['released']) for r in rows)/100
    settled=sum(r['settled'] for r in rows)/100
    invested=db.execute("SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM budget_investment_transfers WHERE direction='OUT' AND substr(date,1,7)=?",(month,)).fetchone()[0]
    return round(spent+newly_allocated-settled+invested,2),round(invested,2)


def monthly_budget_totals(db, month):
    from budget_reserves_service import reserved_cents
    from expected_income_service import pending_amount_cents
    from budget_planning_service import reserve_plans
    balance = db.execute('SELECT COALESCE(SUM(balance), 0) FROM budget_accounts').fetchone()[0]
    flows = db.execute('''
        SELECT COALESCE(SUM(CASE WHEN kind = 'INCOME' THEN amount_cents ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN kind = 'EXPENSE' THEN amount_cents ELSE 0 END), 0)
        FROM budget_entries_v2 WHERE substr(date, 1, 7) = ?
    ''', (month,)).fetchone()
    planned = round(sum(c['planned'] for c in category_workspace(db, month) if c['parent_id'] is None), 2)
    month_end = f"{month}-{calendar.monthrange(*map(int, month.split('-')))[1]:02d}"
    later = db.execute('''
        SELECT COALESCE(SUM(cash_effect * CASE WHEN kind = 'INCOME' THEN amount_cents ELSE -amount_cents END), 0)
        FROM budget_entries_v2 WHERE date > ?
    ''', (month_end,)).fetchone()[0]
    later += db.execute('''
        SELECT COALESCE(SUM(CASE WHEN direction = 'IN' THEN amount_cents ELSE -amount_cents END), 0)
        FROM budget_investment_transfers WHERE date > ?
    ''', (month_end,)).fetchone()[0]
    from budget_refunds_service import flows as net_flows
    net=net_flows(db,month+'-01',month_end)
    income, spent = net[0]/100, net[1]/100
    later += db.execute('SELECT COALESCE(SUM(difference_cents),0) FROM budget_account_reconciliations WHERE date>?', (month_end,)).fetchone()[0]
    reserved = reserved_cents(db, through=month_end) / 100
    allocation = reserve_budget_costs(db, month+'-01', month_end)
    expected_income = pending_amount_cents(db, month+'-01', month_end) / 100
    monthly_reserves=reserve_plans(db,month)
    reserve_remaining = round(sum(r['remaining'] for r in monthly_reserves),2)
    from budget_bill_schedule import due_in_month,amount_cents
    from budget_bill_funding import occurrence
    covered={}
    for bill in db.execute('SELECT * FROM budget_bills_v2 WHERE active=1 AND reserve_id IS NOT NULL'):
        if due_in_month(bill,month):
            value=occurrence(db,bill,month)
            reserve=db.execute('SELECT open_ended FROM budget_reserves WHERE id=?',(bill['reserve_id'],)).fetchone()
            if not value['paid'] and reserve and not reserve['open_ended']:
                covered[bill['reserve_id']]=value['unfunded_cents']
    # A bill due this month already includes its unfunded portion in the category
    # plan. A monthly reserve contribution earmarking that portion is the same cost.
    reserve_extra=round(sum(max(0,round(r['remaining']*100)-covered.get(r['reserve_id'],0)) for r in monthly_reserves if r.get('monthly_amount') is None or r.get('open_ended'))/100,2)
    categories=category_workspace(db,month)
    from budget_loan_plan_service import items as loan_items
    loans,loan_warnings=loan_items(db,month)
    from budget_commitments_service import pending_by_root
    outstanding=pending_by_root(db,month,categories,loans)
    remaining=round(sum(max(0,round(c['remaining']*100),outstanding.get(c['id'],0)) for c in categories if c['parent_id'] is None)/100+outstanding.get(None,0)/100,2)
    planned=round(planned+sum(l['amount'] for l in loans if l['category_id'] is None),2)
    month_cost,month_invested=month_income_cost(db,month,spent)
    income_total=round(income+expected_income,2)
    remaining_month_plan=round(remaining+reserve_extra,2)
    from budget_account_types import totals as account_totals
    return {
        **account_totals(db),
        'monthly_income_total':income_total,'monthly_income_cost':month_cost,
        'monthly_income_remaining_plan':remaining_month_plan,'monthly_invested':month_invested,
        'monthly_income_to_plan':round(income_total-month_cost-remaining_month_plan,2),
        'period_spending': period_spending(db, month),
        'balance': round(balance, 2), 'income': income, 'planned': planned, 'spent': spent,
        'expected_income': expected_income,
        'refunds': net[2]/100, 'remaining_commitments': remaining, 'loan_warnings': loan_warnings,
        'available_now': round(balance-reserved_cents(db)/100,2), 'reserve_plan_remaining': reserve_remaining,
        'reserve_plan_extra': reserve_extra,
        **allocation, 'budget_spent': round(spent+allocation['reserve_adjustment'],2),
        'budget_net': round(income-spent-allocation['reserve_adjustment'],2),
        'remaining_in_plan': round(planned-spent-sum(c['spent']-c['actual_spent'] for c in categories if c['parent_id'] is None),2),
        'reserved': reserved,
        'to_plan': round(balance - later / 100 + expected_income - remaining - reserved-reserve_extra, 2),
    }

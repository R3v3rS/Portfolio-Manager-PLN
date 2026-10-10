"""Reconcile the common monthly table with the same ledger as budget totals."""
from collections import defaultdict


def rows(db, month, categories, bills, loans, reserves, totals):
    done = defaultdict(int)
    media=[r for r in reserves if r.get('monthly_amount') is not None and not r.get('open_ended')]
    ordinary=[r for r in reserves if r.get('monthly_amount') is None or r.get('open_ended')]
    media_ids={r['category_id'] for r in media}
    media_bill_ids={b['id'] for b in bills if b['reserve_id'] in {r['reserve_id'] for r in media}}
    roots={c['id']:c['parent_id'] or c['id'] for c in categories}
    for entry in db.execute('''SELECT e.*,r.purchase_entry_id FROM budget_entries_v2 e
        LEFT JOIN budget_purchase_refunds r ON r.entry_id=e.id WHERE substr(e.date,1,7)=?''', (month,)):
        if entry['kind'] != 'EXPENSE' and not entry['purchase_entry_id']:
            continue
        original = entry['purchase_entry_id'] or entry['id']
        kind = 'DAILY'
        if db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE entry_id=?', (original,)).fetchone():
            kind = 'BILLS'
        elif db.execute('SELECT 1 FROM loan_installment_payments WHERE budget_entry_id=? UNION ALL SELECT 1 FROM loan_overpayments WHERE budget_entry_id=?', (original, original)).fetchone():
            kind = 'LOANS'
        elif db.execute('SELECT 1 FROM budget_reserve_movements WHERE budget_entry_id=?', (original,)).fetchone():
            kind = 'RESERVE_COST'
        media_amount=sum(line['amount_cents'] for line in db.execute('SELECT category_id,amount_cents FROM budget_entry_lines_v2 WHERE entry_id=?',(entry['id'],)) if line['category_id'] in media_ids)
        sign=-1 if entry['purchase_entry_id'] else 1
        done[kind] += (entry['amount_cents']-media_amount)*sign
        done['MEDIA'] += media_amount*sign
    from budget_media_service import category_adjustments
    done['MEDIA']+=sum(category_adjustments(db,month,month+'-31').values())
    daily_plan = round(sum(max(0,c['planned']-c['planned_bills']) for c in categories if not c['parent_id']),2)
    from budget_commitments_service import pending_by_root
    outstanding=pending_by_root(db,month,categories,loans,include_monthly=False)
    media_left=defaultdict(int)
    for r in media:media_left[roots[r['category_id']]]+=round(r['remaining']*100)
    daily_remaining=sum(max(0,round(c['remaining']*100)-outstanding.get(c['id'],0)-media_left[c['id']]) for c in categories if not c['parent_id'])/100
    def row(kind, name, planned, performed, left):
        return dict(kind=kind,name=name,planned=round(planned,2),done=round(performed,2),remaining=round(left,2))
    result = [
        row('INCOME','Wpływy',totals['income']+totals['expected_income'],totals['income'],totals['expected_income']),
        row('DAILY','Codzienne wydatki',daily_plan,done['DAILY']/100,daily_remaining),
        row('BILLS','Rachunki poza pulami mediów',sum(b['amount'] for b in bills if b['id'] not in media_bill_ids),done['BILLS']/100,sum(b['amount'] for b in bills if b['status']!='PAID' and b['id'] not in media_bill_ids)),
        row('LOANS','Raty i nadpłaty kredytów',sum(l['amount'] for l in loans),done['LOANS']/100,sum(l['amount'] for l in loans if not l['paid'])),
        row('RESERVES','Odłożenia na rezerwy',sum(r['planned'] for r in ordinary),sum(r['funded'] for r in ordinary),sum(r['remaining'] for r in ordinary)),
    ]
    if media:
        result.append(row('MEDIA','Media — płatności i odłożenia',sum(r['planned'] for r in media),done['MEDIA']/100,sum(r['remaining'] for r in media)))
    if done['RESERVE_COST']:
        result.append(row('RESERVE_COST','Płatności z rezerw bez rachunku',0,done['RESERVE_COST']/100,0))
    # Payment and allocation are distinct activities; their monthly costs sum
    # without counting an earmarked payment a second time.
    for item in result:
        item['month_cost']=None if item['kind']=='INCOME' else item['done']
    for item in result:
        if item['kind'] not in ('BILLS','RESERVE_COST'):continue
        settled=sum(m['settled'] for m in db.execute("""SELECT m.reserve_id,-m.budget_cost_cents settled
            FROM budget_reserve_movements m WHERE m.kind='SPEND' AND substr(m.date,1,7)=?
            AND m.budget_entry_id IS NOT NULL AND EXISTS(SELECT 1 FROM budget_bill_payments_v2 b WHERE b.entry_id=m.budget_entry_id)=?""",
            (month,int(item['kind']=='BILLS'))) if m['reserve_id'] not in {r['reserve_id'] for r in media})
        item['month_cost']=round(item['done']-settled/100,2)
    return result

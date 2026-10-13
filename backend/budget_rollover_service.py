"""Virtual category carryovers; reserving actual money requires month closing."""
import calendar
from collections import defaultdict


def freeze_legacy_closings(db):
    """Keep existing explicit choices; fill older automatic choices from their saved basis."""
    import json
    for closing in db.execute('''SELECT c.id,c.month,s.snapshot_json FROM budget_month_closings c
        JOIN budget_month_snapshots s ON s.month=c.month''').fetchall():
        for category in json.loads(closing['snapshot_json'])['categories']:
            root=db.execute('SELECT parent_id FROM budget_categories_v2 WHERE id=?',(category['id'],)).fetchone()
            if not root or root['parent_id'] is not None:continue
            policy=db.execute('SELECT * FROM budget_category_policies WHERE category_id=? AND start_month<=?',(category['id'],closing['month'])).fetchone()
            media=db.execute('''SELECT 1 FROM budget_reserves WHERE category_id=? AND monthly_amount_cents IS NOT NULL
                AND open_ended=0 AND is_archived=0 AND COALESCE(monthly_start_month,substr(start_date,1,7))<=?''',(category['id'],closing['month'])).fetchone()
            destination='ROLLOVER' if policy and policy['mode']=='ROLLOVER' and not policy['decision_required'] and not media else 'RESET'
            db.execute('''INSERT OR IGNORE INTO budget_month_closing_items
                (closing_id,category_id,amount_cents,destination) VALUES(?,?,?,?)''',
                (closing['id'],category['id'],max(0,round(category['remaining']*100)),destination))


def carries(db, month, options):
    from budget_bill_schedule import category_bill_cents
    from budget_category_hierarchy_service import plan_amounts
    decisions={(r['month'],r['category_id']):dict(r) for r in db.execute('''SELECT m.month,i.* FROM budget_month_closing_items i
        JOIN budget_month_closings m ON m.id=i.closing_id WHERE m.month<?''',(month,))}
    by_id={r['category_id']:dict(r) for r in db.execute("SELECT * FROM budget_category_policies WHERE (mode='ROLLOVER' OR decision_required=1) AND start_month<?",(month,))}
    for (period,category_id),decision in decisions.items():
        if decision['destination']=='ROLLOVER' and category_id not in by_id:
            by_id[category_id]=dict(category_id=category_id,start_month=period,mode='RESET',decision_required=0)
    policies=list(by_id.values())
    media_categories={r['category_id'] for r in db.execute('SELECT category_id FROM budget_reserves WHERE monthly_amount_cents IS NOT NULL AND open_ended=0 AND is_archived=0 AND COALESCE(monthly_start_month,substr(start_date,1,7))<=?',(month,))}
    result={c['id']:0 for c in options}
    if not policies: return result
    start=min([p['start_month'] for p in policies]+[key[0] for key in decisions if key[1] in by_id])
    year,current=map(int,start.split('-'))
    spent=defaultdict(dict)
    for r in db.execute('''SELECT substr(e.date,1,7) month,l.category_id,SUM(CASE WHEN e.kind='EXPENSE' THEN l.amount_cents ELSE -l.amount_cents END) amount
        FROM budget_entry_lines_v2 l JOIN budget_entries_v2 e ON e.id=l.entry_id
        WHERE (e.kind='EXPENSE' OR EXISTS(SELECT 1 FROM budget_purchase_refunds r WHERE r.entry_id=e.id)) AND substr(e.date,1,7)>=? AND substr(e.date,1,7)<?
        GROUP BY substr(e.date,1,7),l.category_id''',(start,month)):
        spent[r['month']][r['category_id']]=r['amount']
    while (key:=f'{year:04d}-{current:02d}')<month:
        fixed=category_bill_cents(db,key)
        from budget_media_service import category_targets,category_adjustments
        from budget_default_plan_service import resolve
        own_manual,_=resolve(db,key)
        for category_id,amount in category_targets(db,key).items():
            fixed[category_id]=fixed.get(category_id,0)+amount
            own_manual[category_id]=0
        period_spent=dict(spent[key])
        for category_id,amount in category_adjustments(db,key,key+'-31').items():
            period_spent[category_id]=period_spent.get(category_id,0)+amount
        from budget_loan_plan_service import items
        loans,_=items(db,key)
        for loan in loans:
            if loan['category_id'] is not None: fixed[loan['category_id']]=fixed.get(loan['category_id'],0)+round(loan['amount']*100)
        amounts=plan_amounts(options,own_manual,fixed)
        from budget_bill_funding import category_coverage
        coverage,settled=category_coverage(db,key)
        gross={i:value+coverage.get(i,0) for i,value in fixed.items()}
        for i,value in coverage.items():gross.setdefault(i,value)
        amounts=plan_amounts(options,own_manual,gross)
        for i,value in settled.items():period_spent[i]=period_spent.get(i,0)-value
        snapshot=db.execute('SELECT snapshot_json FROM budget_month_snapshots WHERE month=?',(key,)).fetchone()
        if snapshot:
            import json
            frozen={c['id']:c for c in json.loads(snapshot['snapshot_json'])['categories']}
        else: frozen={}
        for policy in policies:
            decision=decisions.get((key,policy['category_id']))
            if decision:
                result[policy['category_id']]=decision['amount_cents'] if decision['destination']=='ROLLOVER' else 0
                continue
            if policy['start_month']>key or policy['mode']!='ROLLOVER' or policy['decision_required'] or policy['category_id'] in media_categories:
                result[policy['category_id']]=0
                continue
            ids=[c['id'] for c in options if c['id']==policy['category_id'] or c['parent_id']==policy['category_id']]
            result[policy['category_id']]=max(0,round(frozen[policy['category_id']]['remaining']*100)) if policy['category_id'] in frozen else max(0,amounts.get(policy['category_id'],0)-sum(coverage.get(i,0) for i in ids)+result.get(policy['category_id'],0)-sum(period_spent.get(i,0) for i in ids))
        year,current=(year+1,1) if current==12 else (year,current+1)
    return result

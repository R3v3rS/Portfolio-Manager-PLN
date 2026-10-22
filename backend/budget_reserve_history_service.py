"""One chronological journal and a reconciled monthly cash-earmark statement."""
import json
from uuid import UUID, uuid5

from database import get_db


def enrich_workspace(workspace, month=None):
    from routes_budget_workspace import month_value
    month = month_value(month or workspace['as_of'][:7])
    db = get_db()
    receipts = {r['request_id']: json.loads(r['result_json']) for r in db.execute(
        "SELECT * FROM budget_reserve_operation_receipts WHERE cancelled=0 AND kind!='BATCH'")}
    all_settlements = list(db.execute('SELECT * FROM budget_settlements WHERE reserve_id IS NOT NULL'))
    from budget_planning_service import reserve_plans
    plans={p['reserve_id']:p for p in reserve_plans(db,month)}
    relocated = {}
    for s in all_settlements:
        extra = json.loads(s['before_json'] or '{}').get('_surplus_transfer')
        if extra:
            for i in extra['movement_ids']:
                relocated[i] = s['entry_id']
    for item in workspace['items']:
        movements = list(db.execute('''SELECT m.*,a.name account_name,e.amount_cents expense_cents,e.cash_effect
            FROM budget_reserve_movements m JOIN budget_accounts a ON a.id=m.account_id
            LEFT JOIN budget_entries_v2 e ON e.id=m.budget_entry_id
            WHERE m.reserve_id=? ORDER BY m.date,m.id''',(item['id'],)))
        by_id = {m['id']:m for m in movements}
        grouped = {}
        for s in all_settlements:
            if s['reserve_id']==item['id']:
                ids = json.loads(s['movement_ids'])
                for i in ids:
                    grouped[i] = ids
        transfers = list(db.execute('''SELECT t.*,s.name source_name,a.name target_name FROM budget_account_transfers t
            JOIN budget_accounts s ON s.id=t.source_account_id JOIN budget_accounts a ON a.id=t.target_account_id
            WHERE t.reserve_id=? ORDER BY t.date,t.id''',(item['id'],)))
        funding = {str(uuid5(UUID(t['request_id']),'reserve-funding')):t for t in transfers if t['reserve_action']=='FUND'}
        events=[]; consumed=set()
        statement=dict(month=month,opening=0,added=0,used=0,released=0,payments=0,ending=0)
        for m in movements:
            delta=m['amount_cents'] if m['kind']=='ADD' else -m['amount_cents']
            if m['date'][:7]<month:
                statement['opening']+=delta
            if m['date'][:7]<=month:
                statement['ending']+=delta
            if m['date'][:7]==month and m['kind']!='SPEND':
                statement['added' if m['kind']=='ADD' else 'released']+=m['amount_cents']
            if m['id'] in consumed:
                continue
            group=[by_id[i] for i in grouped.get(m['id'],[m['id']]) if i in by_id]
            consumed.update(r['id'] for r in group)
            first=next((r for r in group if r['budget_entry_id']),m)
            removed=sum(r['amount_cents'] for r in group)
            summary=receipts.get(first['request_id'],{}).get('summary')
            title={'ADD':'Odłożenie','RELEASE':'Zwolnienie środków','SPEND':'Rozliczenie płatności'}[m['kind']]
            kind=m['kind']
            if m['kind']=='SPEND':
                payment=first['expense_cents'] or 0
                used=min(removed,payment)
                if m['date'][:7]==month:
                    statement['used']+=used
                    statement['released']+=removed-used
                    statement['payments']+=payment
                if not summary:
                    before_saved=sum(r['amount_cents'] if r['kind']=='ADD' else -r['amount_cents'] for r in movements if r['id']<min(g['id'] for g in group))
                    summary=dict(kind='SPEND',date=m['date'],reserve_name=item['name'],reserve_id=item['id'],amount=payment/100,
                        reserve_before=before_saved/100,reserve_after=(before_saved-removed)/100,
                        covered=used/100,released=removed/100,surplus=max(0,before_saved-payment)/100,
                        surplus_mode='FREE' if removed>payment else 'KEEP',surplus_reserve_name=None,
                        accounts=[],budget_entry_id=first['budget_entry_id'])
            transfer=funding.get(m['request_id'])
            if transfer:
                title='Przelew i odłożenie';kind='FUND'
            if m['id'] in relocated:
                title='Nadwyżka z innej rezerwy';kind='REALLOCATE'
            expense=first['expense_cents'] if m['kind']=='SPEND' else None
            cash_effect=-expense/100 if expense is not None and first['cash_effect'] else 0
            if summary is not None and 'existing_expense' in summary and summary['existing_expense']:
                cash_effect=0
            events.append(dict(id=f'm:{m["id"]}',kind=kind,title=title,date=m['date'],created_at=m['created_at'],
                amount=(expense if expense is not None else m['amount_cents'])/100,
                reserve_change=(m['amount_cents'] if m['kind']=='ADD' else -removed)/100,
                bank_change=cash_effect,account_name=m['account_name'],notes=m['notes'],
                transfer=dict(source=transfer['source_name'],target=transfer['target_name'],changes_cash=bool(transfer['move_money'] and transfer['cash_effect'])) if transfer else None,
                budget_entry_id=first['budget_entry_id'],summary=summary))
        for t in transfers:
            if t['reserve_action']=='FUND':
                continue # The matching ADD is shown together with its bank transfer.
            events.append(dict(id=f't:{t["id"]}',kind='TRANSFER',title='Przelew odłożonych środków' if t['move_money'] else 'Zmiana miejsca rezerwy',
                date=t['date'],created_at=t['created_at'],amount=t['amount_cents']/100,reserve_change=0,bank_change=0,
                account_name=f'{t["source_name"]} → {t["target_name"]}',notes=t['notes'],
                transfer=dict(source=t['source_name'],target=t['target_name'],changes_cash=bool(t['move_money'] and t['cash_effect'])),budget_entry_id=None,summary=None))
        for r in db.execute('SELECT * FROM budget_settlement_reversals'):
            audit=json.loads(r['audit_json'])
            settlement=audit.get('settlement')
            if settlement and settlement['reserve_id']==item['id']:
                events.append(dict(id=f'u:{r["request_id"]}',kind='REVERSAL',title='Cofnięcie rozliczenia',date=r['reversed_at'][:10],
                    created_at=r['reversed_at'],amount=audit['entry']['amount_cents']/100,reserve_change=0,bank_change=0,
                    account_name='',notes='Rozliczenie cofnięte; zestawienie obejmuje aktualne zapisy.',transfer=None,budget_entry_id=None,summary=None))
        item['journal']=sorted(events,key=lambda e:(e['date'],e['created_at'],e['id']),reverse=True)
        item['month_statement']={k:v/100 if k!='month' else v for k,v in statement.items()}
        p=plans.get(item['id'],{})
        item['month_statement'].update(planned=p.get('planned',0),funded=min(p.get('funded',0),p.get('planned',0)),
            extra=round(max(0,p.get('contributed',p.get('funded',0))-p.get('planned',0)),2),remaining=p.get('remaining',0))
    workspace['month']=month
    return workspace

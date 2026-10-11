"""A closing records its basis; later corrections remain visible and comparable."""
import json


def capture(db,month):
    from budget_category_hierarchy_service import category_workspace
    from budget_planning_service import reserve_plans
    from budget_refunds_service import flows
    income,spent,refunds=flows(db,month+'-01',month+'-31')
    return dict(income=income/100,spent=spent/100,refunds=refunds/100,
        categories=[dict(id=c['id'],planned=c['planned'],spent=c['spent'],remaining=c['remaining']) for c in category_workspace(db,month)],
        reserves=[dict(id=r['reserve_id'],planned=r['planned'],contributed=r['contributed'],funded=r['funded']) for r in reserve_plans(db,month)],
        entries=[dict(r) for r in db.execute('SELECT id,version FROM budget_entries_v2 WHERE substr(date,1,7)=? ORDER BY id',(month,))])


def comparison(db,month):
    row=db.execute('SELECT * FROM budget_month_snapshots WHERE month=?',(month,)).fetchone()
    if not row: return None
    original=json.loads(row['snapshot_json']);current=capture(db,month)
    return dict(recorded_at=row['recorded_at'],changed=original!=current,
        original=original,current=current,differences={key:round(current[key]-original[key],2) for key in ('income','spent','refunds')})

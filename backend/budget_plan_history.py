"""Preserve completed plans before changing reserve configuration or cycles."""
import json


def freeze(db, reserve_id, include_current=False):
    from budget_reserves_service import date
    from budget_planning_service import reserve_plans, shift_month
    reserve=db.execute('SELECT * FROM budget_reserves WHERE id=?',(reserve_id,)).fetchone()
    month=reserve['start_date'][:7]
    last=date.today().strftime('%Y-%m')
    while month<last or (include_current and month==last):
        existing=db.execute('SELECT 1 FROM budget_reserve_plan_history WHERE reserve_id=? AND month=?',(reserve_id,month)).fetchone()
        if not existing or month==last:
            row=next((r for r in reserve_plans(db,month) if r['reserve_id']==reserve_id),None)
            if row:
                db.execute('''INSERT INTO budget_reserve_plan_history(reserve_id,month,plan_json) VALUES(?,?,?)
                    ON CONFLICT(reserve_id,month) DO UPDATE SET plan_json=excluded.plan_json''',
                    (reserve_id,month,json.dumps(row,ensure_ascii=False)))
        month=shift_month(month,1)

"""Shared regression fixtures; use only the disposable database supplied by tests."""
from uuid import uuid4
from tests.test_budget_reserves import FrozenDate
from database import get_db


def linked_open(c):
    reserve=c.create_reserve(name='Stala rezerwa',open_ended=True,monthly_amount=100)
    c.result(c.move(reserve,'ADD',100),201)
    FrozenDate.current=FrozenDate(2026,11,3)
    bill=c.bill(title='Koszt z rezerwy',amount=100,start_month='2026-11',reserve_id=reserve)
    c.result(c.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-11',date='2026-11-03',amount=100,version=1,reserve_version=c.item(reserve)['version'],request_id=str(uuid4()))),201)
    w=c.get_workspace('2026-11');f=c.forecast()
    return dict(balance=w['totals']['balance'],still_to_save=w['planning']['reserve_plans'][0]['remaining'],to_plan=w['totals']['to_plan'],expected_to_plan=9800,extra=w['totals']['reserve_plan_extra'],forecast_first_add=next(e['amount'] for e in f['events'] if e['kind']=='RESERVE_ADD'))


def media_history(c):
    reserve=c.create_reserve(name='Prad',monthly_amount=250,category_id=c.category)
    c.result(c.move(reserve,'ADD',250),201)
    before=c.get_workspace('2026-10')['planning']['reserve_plans'][0]['planned']
    FrozenDate.current=FrozenDate(2026,11,3)
    c.result(c.client.put(f'{c.base}/{reserve}',json=dict(name='Prad',notes='',account_id=c.account,monthly_amount=300,category_id=c.category,frequency='YEARLY',version=c.item(reserve)['version'])))
    return dict(october_plan_before=before,october_plan_after=c.get_workspace('2026-10')['planning']['reserve_plans'][0]['planned'],october_cash_cost=c.get_workspace('2026-10')['totals']['budget_spent'])


def retry_manual(c):
    payload=dict(kind='EXPENSE',account_id=c.account,amount=100,date='2026-10-03',description='Zakup',lines=[dict(category_id=c.category,amount=100,label='')],request_id=str(uuid4()))
    first=c.result(c.client.post('/api/budget/workspace/entries',json=payload),201)
    second=c.result(c.client.post('/api/budget/workspace/entries',json=payload),201)
    return dict(first=first['id'],second=second['id'],spent=c.get_workspace()['totals']['spent'],balance=c.get_workspace()['totals']['balance'])


def media_retry(c):
    payload=dict(name='Prad',notes='',account_id=c.account,monthly_amount=250,category_id=c.category,frequency='YEARLY',request_id=str(uuid4()))
    first=c.client.post(c.base,json=payload);second=c.client.post(c.base,json=payload)
    return dict(first_status=first.status_code,retry_status=second.status_code,error=second.json.get('error'),reserve_count=get_db().execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0])


def variable_bill(c):
    bill=c.bill(amount=250,variable_amount=True)
    c.result(c.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03',amount=180,version=1,request_id=str(uuid4()))),201)
    w=c.get_workspace()
    return dict(auto_category_plan=w['categories'][0]['planned'],paid_bill_amount=w['bills'][0]['amount'],month_plan=w['planning']['month_plan'],to_plan=w['totals']['to_plan'])


def manual_limit_funded_bill(c):
    reserve=c.create_reserve(name='Ubezpieczenie',target_amount=400,frequency='ONCE',due_date='2026-10-15',category_id=c.category)
    c.result(c.move(reserve,'ADD',400),201)
    bill=c.bill(title='Ubezpieczenie',amount=400,frequency='ONCE',due_month='2026-10',reserve_id=reserve)
    db=get_db();db.execute('INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,?,?)',(c.category,'2026-10',40000));db.commit()
    before=c.get_workspace()['totals']['to_plan']
    c.result(c.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03',amount=400,version=1,reserve_version=c.item(reserve)['version'],request_id=str(uuid4()))),201)
    return dict(to_plan_before_payment=before,to_plan_after_payment=c.get_workspace()['totals']['to_plan'],expected_stable_to_plan=9600,expense=c.get_workspace()['totals']['spent'])

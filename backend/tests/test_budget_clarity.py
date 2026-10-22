import unittest
from uuid import uuid4
from database import get_db
from routes_budget_workspace import insert_entry
from tests import test_budget_planning as fixtures


class BudgetClarityTest(unittest.TestCase):
    setUp=fixtures.BudgetPlanningTest.setUp
    result=fixtures.BudgetPlanningTest.result
    create_reserve=fixtures.BudgetPlanningTest.create_reserve
    item=fixtures.BudgetPlanningTest.item
    move=fixtures.BudgetPlanningTest.move
    bill=fixtures.BudgetPlanningTest.bill
    get_workspace=fixtures.BudgetPlanningTest.get_workspace
    plan=fixtures.BudgetPlanningTest.plan

    def test_shared_limit_separates_bills_and_shopping_without_moving_money_on_read(self):
        db=get_db()
        child=db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Telefon',?)",(self.category,)).lastrowid
        db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-10',100000)",(self.category,));db.commit()
        self.bill(amount=250)
        self.bill(title='Telefon',amount=80,category_id=child)
        insert_entry(db,dict(kind='EXPENSE',account_id=self.account,amount_cents=20000,date='2026-10-03',description='Zakupy',merchant=None,lines=[dict(category_id=self.category,label='',amount_cents=20000)]));db.commit()
        before=db.total_changes
        data=self.get_workspace()
        root=next(c for c in data['categories'] if c['id']==self.category)
        self.assertEqual((root['planned'],root['plan_details']['payments_planned'],root['plan_details']['ordinary_planned']),(1000,330,670))
        self.assertEqual((root['plan_details']['ordinary_spent'],root['plan_details']['ordinary_remaining']),(200,470))
        self.assertEqual(data['totals']['planned'],1000)
        self.assertEqual(db.total_changes,before)

    def test_funded_bill_is_visible_but_does_not_create_another_spending_limit(self):
        reserve=self.create_reserve(frequency='ONCE',target_amount=600,due_date='2026-10-15')
        self.result(self.move(reserve,'ADD',600),201)
        self.bill(frequency='ONCE',due_month='2026-10',due_day=15,amount=600,reserve_id=reserve)
        data=self.get_workspace();root=next(c for c in data['categories'] if c['id']==self.category)
        self.assertEqual(len(data['bills']),1)
        self.assertEqual((root['planned'],root['plan_details']['payments_planned'],root['plan_details']['ordinary_planned'],root['plan_details']['ordinary_remaining']),(0,0,0,0))
        self.assertEqual(root['reserve_covered'],600)

    def test_extra_on_one_reserve_does_not_hide_the_missing_contribution_to_another(self):
        first=self.create_reserve();second=self.create_reserve(name='Dodatkowa',open_ended=True,monthly_amount=0)
        self.result(self.plan(first,amount=100))
        self.result(self.move(first,'ADD',70),201);self.result(self.move(second,'ADD',150),201)
        row=next(r for r in self.get_workspace()['planning']['month_plan'] if r['kind']=='RESERVES')
        self.assertEqual((row['planned'],row['plan_done'],row['remaining'],row['extra']),(100,70,30,150))

    def test_account_transfer_is_in_history_without_becoming_income_or_expense(self):
        db=get_db();other=db.execute("INSERT INTO budget_accounts(name,balance,currency) VALUES('Alior',500,'PLN')").lastrowid
        db.execute('''INSERT INTO budget_account_transfers(source_account_id,target_account_id,move_money,reserve_action,amount_cents,date,notes,request_id,request_payload,created_at)
            VALUES(?,?,1,'MOVE',10000,'2026-10-03','Przeniesienie',?,'{}','2026-10-03')''',(self.account,other,str(uuid4())));db.commit()
        data=self.get_workspace()
        self.assertEqual(data['bank_transfers'][0]['description'],'Przeniesienie')
        self.assertEqual((data['totals']['income'],data['totals']['spent']),(0,0))

    def test_media_payment_uses_one_envelope_and_is_not_shopping(self):
        reserve=self.create_reserve(name='Prąd',monthly_amount=250,category_id=self.category)
        self.result(self.move(reserve,'ADD',250),201)
        self.result(self.move(reserve,'SPEND',180),201)
        data=self.get_workspace();root=next(c for c in data['categories'] if c['id']==self.category)
        self.assertEqual((root['planned'],root['plan_details']['payments_planned'],root['plan_details']['ordinary_planned'],root['plan_details']['ordinary_spent'],root['plan_details']['ordinary_remaining']),(250,250,0,0,0))
        self.assertEqual(data['totals']['to_plan'],9750)

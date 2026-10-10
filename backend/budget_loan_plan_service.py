"""Shared monthly loan commitments for household plans and closing checks."""
from loan_service import LoanService


def items(db, month):
    category=db.execute("SELECT id,parent_id FROM budget_categories_v2 WHERE lower(name)='rachunki' ORDER BY id LIMIT 1").fetchone()
    category_id=(category['parent_id'] or category['id']) if category else None
    result=[];warnings=[]
    for raw in db.execute('''SELECT id,name,original_amount,duration_months,
            CAST(start_date AS TEXT) AS start_date,installment_type,category FROM loans'''):
        loan=dict(raw)
        try:
            rates=LoanService.get_loan_rates(loan['id'])
            if not rates: raise ValueError('Brak oprocentowania')
            schedule,_,_=LoanService.calculate_schedule(loan,rates,LoanService.get_loan_overpayments(loan['id']))
            for row in schedule:
                if row['date'][:7]!=month or row.get('is_mid_month') or row['installment']<=0: continue
                payment=db.execute('SELECT * FROM loan_installment_payments WHERE loan_id=? AND installment_month=?',(loan['id'],row['month'])).fetchone()
                result.append(dict(id=loan['id'],name=loan['name'],date=row['date'],amount=round(row['installment'],2),
                    paid_on=payment['paid_on'] if payment else None,paid_amount=payment['amount_cents']/100 if payment else None,
                    category_id=category_id,paid=bool(payment),installment_month=row['month']))
        except (ValueError,TypeError,IndexError,ZeroDivisionError,OverflowError): warnings.append(f'{loan["name"]}: uzupełnij harmonogram lub oprocentowanie, aby uwzględnić raty w planie.')
    return result,warnings

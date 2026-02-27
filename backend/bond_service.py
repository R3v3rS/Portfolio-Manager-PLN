from database import get_db
from datetime import datetime, date

class BondService:
    @staticmethod
    def add_bond(portfolio_id, name, principal, interest_rate, purchase_date):
        db = get_db()
        try:
            db.execute(
                '''INSERT INTO bonds (portfolio_id, name, principal, interest_rate, purchase_date)
                   VALUES (?, ?, ?, ?, ?)''',
                (portfolio_id, name, principal, interest_rate, purchase_date)
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_bonds(portfolio_id):
        db = get_db()
        bonds = db.execute('SELECT * FROM bonds WHERE portfolio_id = ?', (portfolio_id,)).fetchall()
        
        results = []
        today = date.today()
        
        for b in bonds:
            b_dict = {key: b[key] for key in b.keys()}
            p_date = datetime.strptime(b_dict['purchase_date'], '%Y-%m-%d').date()
            days_passed = (today - p_date).days
            if days_passed < 0: days_passed = 0
            
            # accrued_interest = principal * (interest_rate / 100) * (days_passed / 365)
            accrued = float(b_dict['principal']) * (float(b_dict['interest_rate']) / 100) * (days_passed / 365.0)
            b_dict['accrued_interest'] = round(accrued, 2)
            b_dict['total_value'] = round(float(b_dict['principal']) + accrued, 2)
            results.append(b_dict)
            
        return results

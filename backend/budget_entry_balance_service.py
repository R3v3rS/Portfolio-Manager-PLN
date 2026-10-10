"""Apply an existing historical expense to account cash once."""
from decimal import Decimal

from api.exceptions import ApiError, ValidationError
from budget_category_service import require_version
from database import get_db
from routes_budget_workspace import entry_row


def apply(entry_id, data):
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        entry = entry_row(entry_id)
        if entry['kind'] != 'EXPENSE':
            raise ValidationError('Ta opcja dotyczy tylko wydatków.')
        account = db.execute('SELECT * FROM budget_accounts WHERE id=?', (entry['account_id'],)).fetchone()
        if entry['cash_effect']:
            # A retry after a lost response must never debit the account twice.
            db.rollback()
            return dict(id=entry_id, cash_effect=True, applied=False, version=entry['version'], balance=round(account['balance'], 2))
        require_version(entry, data.get('version'), 'Wydatki')
        for table, column in (('budget_bill_payments_v2', 'entry_id'),
                              ('budget_reserve_movements', 'budget_entry_id'),
                              ('loan_installment_payments', 'budget_entry_id'),
                              ('loan_overpayments', 'budget_entry_id')):
            if db.execute(f'SELECT 1 FROM {table} WHERE {column}=?', (entry_id,)).fetchone():
                raise ValidationError('Ten wydatek rozlicza rachunek, rezerwę lub kredyt. Popraw rozliczenie w odpowiedniej sekcji.')
        expected = data.get('expected_balance')
        if type(expected) not in (int, float) or not Decimal(str(expected)).is_finite():
            raise ValidationError('Podaj aktualne saldo konta z aplikacji.')
        if Decimal(str(expected)) != Decimal(str(round(account['balance'], 2))):
            raise ApiError('budget_entry_balance_conflict', 'Saldo konta zmieniło się. Odśwież dane przed pomniejszeniem salda.', status=409)
        db.execute('UPDATE budget_accounts SET balance=ROUND(balance-?,2) WHERE id=?',
                   (entry['amount_cents']/100, entry['account_id']))
        db.execute('UPDATE budget_entries_v2 SET cash_effect=1,version=version+1 WHERE id=?', (entry_id,))
        balance = db.execute('SELECT ROUND(balance,2) FROM budget_accounts WHERE id=?', (entry['account_id'],)).fetchone()[0]
        db.commit()
        return dict(id=entry_id, cash_effect=True, applied=True, version=entry['version']+1, balance=balance)
    except Exception:
        db.rollback()
        raise

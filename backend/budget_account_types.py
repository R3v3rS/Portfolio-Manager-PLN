"""A card's signed balance is debt, never additional spending power."""
from decimal import Decimal, InvalidOperation

from api.exceptions import ValidationError


def is_credit(account):
    return account['account_type'] == 'CREDIT_CARD'


def balance_cents(value, account_type):
    from routes_budget_workspace import cents
    try:
        if isinstance(value, bool):
            raise ValueError()
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Saldo musi być poprawną kwotą.') from None
    if amount < 0 and account_type != 'CREDIT_CARD':
        raise ValidationError('Ujemne saldo początkowe lub korekta wymaga konta typu karta kredytowa.')
    return (-1 if amount < 0 else 1) * cents(abs(amount), 'Saldo', allow_zero=True)


def require_cash(account):
    if is_credit(account):
        raise ValidationError('Wybierz własne konto bankowe lub gotówkę. Kredytówka służy do zakupów; dochody, odkładanie rezerw i finansowanie przelewów wymagają własnych pieniędzy.')


def totals(db):
    rows = db.execute('SELECT balance,account_type FROM budget_accounts').fetchall()
    cash = sum(round(float(r['balance'])*100) for r in rows if not is_credit(r))
    debt = sum(max(0, -round(float(r['balance'])*100)) for r in rows if is_credit(r))
    credit = sum(max(0, round(float(r['balance'])*100)) for r in rows if is_credit(r))
    return dict(cash_balance=cash/100, credit_card_debt=debt/100, credit_card_overpayment=credit/100)

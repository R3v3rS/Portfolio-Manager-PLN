"""Atomic transfer between a budget account and investment cash, with linked history."""

from datetime import date as date_cls
from decimal import Decimal, InvalidOperation

from api.exceptions import ApiError, ValidationError
from database import get_db
from portfolio_scope import resolve_portfolio_scope


def assert_unlinked_transactions(db, transaction_ids):
    if not transaction_ids:
        return
    if db.execute(f"SELECT 1 FROM transactions t JOIN portfolios p ON p.id=COALESCE(t.sub_portfolio_id,t.portfolio_id) JOIN portfolio_archive_snapshots s ON s.portfolio_id=p.id WHERE t.id IN ({','.join('?' for _ in transaction_ids)}) AND p.is_archived=1 LIMIT 1",transaction_ids).fetchone():
        raise ValidationError('Historia zarchiwizowanej strategii jest zamknięta i nie może zmieniać przypisania.')
    if db.execute(f"SELECT 1 FROM transactions WHERE id IN ({','.join('?' for _ in transaction_ids)}) AND transfer_id LIKE 'archive-cash:%' LIMIT 1",transaction_ids).fetchone():
        raise ValidationError('Transfer przy archiwizacji jest połączoną operacją i nie może zmieniać przypisania.')
    if db.execute(f"SELECT 1 FROM transactions WHERE id IN ({','.join('?' for _ in transaction_ids)}) AND type IN ('ASSET_IN','ASSET_OUT') LIMIT 1",transaction_ids).fetchone():
        raise ValidationError('Przeniesienie akcji jest połączoną operacją. Nie można zmieniać przypisania pojedynczego wpisu. Przenieś akcje nową operacją.')
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='bond_events'").fetchone():
        placeholders=','.join('?' for _ in transaction_ids)
        if db.execute(f'SELECT 1 FROM bond_events WHERE transaction_id IN ({placeholders}) OR extra_transaction_id IN ({placeholders}) LIMIT 1',transaction_ids+transaction_ids).fetchone():
            raise ValidationError('Operacja należy do obligacji. Skoryguj ją w module obligacji, aby zachować zgodność sald.')
    linked = db.execute(
        f"SELECT 1 FROM budget_investment_transfers WHERE investment_transaction_id IN ({','.join('?' for _ in transaction_ids)}) LIMIT 1",
        transaction_ids,
    ).fetchone()
    if linked:
        raise ApiError('LINKED_BUDGET_TRANSFER',
                       'Wpis jest powiązany z budżetem. Przenieś środki osobnym transferem, aby zachować zgodność obu historii.', status=422)


def transfer_investment_cash(account_id, portfolio_id, amount, direction, description,
                             date=None, envelope_id=None, sub_portfolio_id=None, request_id=None, commit=True):
    if direction not in ('OUT','IN'):
        raise ValidationError('Wybierz kierunek transferu do lub z inwestycji.')
    try:
        value = Decimal(str(amount))
        if not value.is_finite() or value <= 0 or value > Decimal('999999999.99') \
                or value != value.quantize(Decimal('0.01')):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise ValidationError('Kwota transferu musi być dodatnia i mieć najwyżej dwa miejsca po przecinku.') from None
    try:
        movement_date = date_cls.fromisoformat(str(date)) if date else date_cls.today()
        if (date and movement_date.isoformat() != str(date)) or movement_date > date_cls.today():
            raise ValueError
    except ValueError:
        raise ValidationError('Podaj poprawną datę transferu, nie późniejszą niż dziś.') from None
    amount_cents = int(value * 100)
    amount = amount_cents / 100
    db = get_db()
    try:
        started_transaction=not db.in_transaction
        if started_transaction: db.execute('BEGIN IMMEDIATE')
        root_id, child_id = resolve_portfolio_scope(db, portfolio_id, sub_portfolio_id)
        target_id = child_id or root_id
        account = db.execute('SELECT * FROM budget_accounts WHERE id = ?', (account_id,)).fetchone()
        if not account:
            raise ValueError('Budget Account not found')
        if (account['currency'] or 'PLN').upper() != 'PLN':
            raise ValidationError('Transfer wymaga konta budżetowego w PLN.')
        portfolio = db.execute('SELECT * FROM portfolios WHERE id = ?', (target_id,)).fetchone()
        if portfolio['is_archived'] or portfolio['account_type'] == 'PPK':
            raise ValidationError('Nie można przenosić gotówki do lub z tego portfela.')
        if request_id:
            previous = db.execute('SELECT * FROM budget_investment_transfers WHERE request_id = ?', (request_id,)).fetchone()
            if previous:
                if (previous['account_id'], previous['portfolio_id'], previous['amount_cents'], previous['direction'], previous['date']) \
                        != (account_id, target_id, amount_cents, direction, movement_date.isoformat()):
                    raise ValidationError('Identyfikator transferu został już użyty dla innej operacji.')
                if started_transaction: db.rollback()
                return previous['id']
        sign = -1 if direction == 'OUT' else 1
        if direction == 'OUT':
            from budget_reserves_service import reserved_cents
            available=round(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(account_id,)).fetchone()[0]*100)-reserved_cents(db,account_id)
            if amount_cents>max(0,available):
                raise ValidationError('Wpłata do inwestycji przekracza środki poza rezerwami. Najpierw zwolnij odłożoną kwotę, jeśli chcesz ją zainwestować.')
            updated = db.execute('UPDATE budget_accounts SET balance = ROUND(balance - ?, 2) WHERE id = ? AND balance >= ?',
                                 (amount, account_id, amount))
        else:
            updated = db.execute('UPDATE portfolios SET current_cash = ROUND(current_cash - ?, 2) WHERE id = ? AND current_cash >= ?',
                                 (amount, target_id, amount))
        if updated.rowcount != 1:
            raise ValidationError('Brak wystarczających środków na koncie źródłowym.')
        if envelope_id:
            envelope = db.execute('SELECT account_id FROM envelopes WHERE id = ?', (envelope_id,)).fetchone()
            if not envelope or envelope['account_id'] != account_id:
                raise ValidationError('Koperta nie należy do wybranego konta.')
            db.execute('UPDATE envelopes SET balance = balance - ? WHERE id = ?', (amount, envelope_id))
        if direction == 'OUT':
            db.execute('UPDATE portfolios SET current_cash = ROUND(current_cash + ?, 2), total_deposits = ROUND(total_deposits + ?, 2) WHERE id = ?',
                       (amount, amount, target_id))
        else:
            db.execute('UPDATE budget_accounts SET balance = ROUND(balance + ?, 2) WHERE id = ?', (amount, account_id))
        description = description or f"Transfer: {account['name']} ↔ {portfolio['name']}"
        investment = db.execute('''
            INSERT INTO transactions (portfolio_id, sub_portfolio_id, ticker, type, quantity, price, total_value, date)
            VALUES (?, ?, 'CASH', ?, 1, ?, ?, ?)
        ''', (root_id, child_id, 'DEPOSIT' if direction == 'OUT' else 'WITHDRAW', amount, amount, movement_date.isoformat()))
        legacy = db.execute('''
            INSERT INTO budget_transactions (type, amount, account_id, envelope_id, description, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('EXPENSE' if sign < 0 else 'INCOME', amount, account_id, envelope_id, description, movement_date.isoformat()))
        transfer = db.execute('''
            INSERT INTO budget_investment_transfers
                (account_id, portfolio_id, investment_transaction_id, budget_transaction_id, direction, amount_cents, date, description, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (account_id, target_id, investment.lastrowid, legacy.lastrowid, direction, amount_cents,
              movement_date.isoformat(), description, request_id))
        db.execute('DELETE FROM portfolio_history_cache WHERE portfolio_id IN (?, ?)', (root_id, target_id))
        if db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'analytics_cache'").fetchone():
            db.execute('DELETE FROM analytics_cache WHERE portfolio_id IN (?, ?)', (root_id, target_id))
        if commit: db.commit()
        return transfer.lastrowid
    except Exception:
        db.rollback()
        raise

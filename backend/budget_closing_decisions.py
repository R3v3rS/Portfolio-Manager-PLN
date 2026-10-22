"""Explicit destinations for unused limits, within the month closing transaction."""
from uuid import UUID, uuid5
from api.exceptions import ValidationError


def destination(db, policy, choice, amount, token, today):
    from routes_budget_workspace import positive_id
    from budget_reserves_service import _account, _now
    if not isinstance(choice, dict):
        raise ValidationError('Wybierz przeznaczenie niewykorzystanego limitu przy zamknięciu miesiąca.')
    kind = choice.get('destination')
    if kind not in ('RESET', 'ROLLOVER', 'RESERVE', 'SAVINGS', 'INVESTMENTS'):
        raise ValidationError('Wybierz przeznaczenie niewykorzystanego limitu.')
    if kind in ('RESET', 'ROLLOVER'):
        return kind, None
    if kind == 'RESERVE':
        reserve_id = positive_id(choice.get('reserve_id'), 'rezerwę')
        row = db.execute('SELECT * FROM budget_reserves WHERE id=? AND is_archived=0 AND completed_at IS NULL', (reserve_id,)).fetchone()
        if not row:
            raise ValidationError('Wybierz aktywną rezerwę.')
        return kind, reserve_id
    account_id = positive_id(choice.get('account_id'), 'konto z odkładanymi pieniędzmi')
    _account(db, account_id)
    if not amount:
        return kind, None
    name = 'Oszczędności z niewykorzystanych limitów' if kind == 'SAVINGS' else 'Środki na przyszłe inwestycje'
    row = db.execute('SELECT id FROM budget_reserves WHERE name=? AND account_id=? AND open_ended=1 AND is_archived=0 AND completed_at IS NULL', (name, account_id)).fetchone()
    if row:
        return kind, row['id']
    now = _now()
    reserve_id = db.execute('''INSERT INTO budget_reserves
        (name,notes,account_id,target_cents,start_date,due_date,anniversary,frequency,request_id,request_payload,created_at,updated_at,open_ended,monthly_amount_cents,monthly_start_month)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,0,?)''',
        (name, 'Wydzielone pieniądze; bez przelewu bankowego ani zakupu inwestycji.', account_id, 1, today, today, today,
         'ONCE', str(uuid5(UUID(token), f'purpose-{policy["category_id"]}')), '{}', now, now, today[:7])).lastrowid
    return kind, reserve_id

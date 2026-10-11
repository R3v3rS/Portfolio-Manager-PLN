"""Actionable reminders from stored records, plus independent personal tasks.

Reading this workspace never books payments, changes a portfolio or fetches quotes.
"""
import calendar
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

from api.exceptions import ApiError, NotFoundError, ValidationError
from budget_summary_service import monthly_budget_totals
from database import get_db
from loan_service import LoanService

CATEGORIES = ('investments', 'budget', 'loans', 'other')


def _action(key, source, category, title, description, due=None, href=None,
            action_label=None, amount=None, priority='normal', **extra):
    return dict(key=key, source=source, category=category, title=title,
                description=description, due_date=due, href=href,
                action_label=action_label, amount=amount, priority=priority, **extra)


def _months(first, last):
    year, month = map(int, first.split('-'))
    while f'{year:04d}-{month:02d}' <= last:
        yield f'{year:04d}-{month:02d}'
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def workspace():
    db = get_db()
    today = date.today()
    horizon = today + timedelta(days=30)
    month = today.strftime('%Y-%m')
    items = []
    warnings = []
    from bond_service import BondService
    for p in db.execute("SELECT id FROM portfolios WHERE account_type='BONDS' AND is_archived=0 AND parent_portfolio_id IS NULL"):
        for bond in BondService.get_bonds(p['id']):
            if not bond['remaining_quantity'] or bond['status']=='VOID':continue
            href=f"/portfolio/{p['id']}?bond={bond['id']}"
            if bond['warnings']:
                items.append(_action(f"bond-rate:{bond['id']}",'bond','investments',f"Sprawdź warunki: {bond['name']}",
                    'Wycena wymaga uzupełnienia warunków lub stopy dla bieżącego okresu.',href=href,action_label='Sprawdź obligacje'))
            due=bond['maturity_date']
            if due and due<=horizon.isoformat():
                items.append(_action(f"bond-maturity:{bond['id']}",'bond','investments',f"Rozlicz wykup: {bond['name']}",
                    'Termin umowny wykupu. Zapisz rzeczywiście otrzymaną kwotę; szacunek nie zmienia salda.',due,href,'Otwórz zakup',bond['estimated_value_net']))
            for period in bond['periods']:
                if period['pays_cash'] and not period['capitalizes'] and not period['paid'] and period['end_date']<=horizon.isoformat():
                    items.append(_action(f"bond-coupon:{bond['id']}:{period['period']}",'bond','investments',f"Sprawdź odsetki: {bond['name']}",
                        f"Okres {period['period']}. Kwota szacunkowa netto; potwierdź faktyczną wypłatę.",period['end_date'],href,'Rozlicz odsetki',period['net']))
                    break
    for row in db.execute('''SELECT id, title, ticker, review_date FROM investor_journal
            WHERE is_archived=0 AND status!='CLOSED' AND review_date<=?''', (horizon.isoformat(),)):
        items.append(_action(f'journal:{row["id"]}', 'journal', 'investments',
            f'Przejrzyj tezę: {row["title"]}',
            f'{row["ticker"] + " · " if row["ticker"] else ""}Zapisz przegląd, wnioski i kolejny termin.',
            row['review_date'], f'/journal?entry={row["id"]}', 'Dodaj przegląd'))

    for row in db.execute('''SELECT n.ticker, n.review_date FROM radar_notes n
            WHERE n.review_date<=? AND (EXISTS(SELECT 1 FROM watchlist w WHERE w.ticker=n.ticker)
            OR EXISTS(SELECT 1 FROM holdings h JOIN portfolios p ON p.id=h.portfolio_id
                WHERE h.ticker=n.ticker AND h.quantity>0 AND p.is_archived=0))''', (horizon.isoformat(),)):
        items.append(_action(f'radar:{row["ticker"]}', 'radar', 'investments',
            f'Przejrzyj obserwację: {row["ticker"]}', 'Sprawdź notatkę i warunki swojej tezy w radarze.',
            row['review_date'], '/radar?' + urlencode({'ticker': row['ticker']}), 'Otwórz obserwację'))

    paid_bills = {(r['bill_id'], r['month']) for r in db.execute('SELECT bill_id, month FROM budget_bill_payments_v2')}
    for row in db.execute('''SELECT b.*, a.name AS account_name FROM budget_bills_v2 b
            JOIN budget_accounts a ON a.id=b.account_id WHERE b.active=1'''):
        from budget_bill_schedule import due_in_month,amount_cents
        for field,title in (('notice_date','Sprawdź termin wypowiedzenia'),('promotion_end','Kończy się promocja')):
            if row[field] and today.isoformat()<=row[field]<=horizon.isoformat():
                items.append(_action(f'bill-{field}:{row["id"]}', 'subscription', 'budget',f'{title}: {row["title"]}',
                    row['notes'] or 'Sprawdź warunki i dalszy koszt zobowiązania.',row[field],
                    '/budget?view=bills', 'Otwórz zobowiązanie'))
        months = [row['due_month']] if row['frequency'] == 'ONCE' else _months(row['start_month'] or month, horizon.strftime('%Y-%m'))
        # Show the oldest outstanding occurrence, including previous months. Once recorded,
        # the next occurrence becomes actionable; do not fabricate history for legacy bills.
        for occurrence in months:
            if not due_in_month(row,occurrence):continue
            if (row['id'], occurrence) in paid_bills:
                continue
            y, m = map(int, occurrence.split('-'))
            due = date(y, m, min(row['due_day'], calendar.monthrange(y, m)[1]))
            if due > horizon:
                continue
            items.append(_action(f'bill:{row["id"]}:{occurrence}', 'bill', 'budget',
                f'Rozlicz rachunek: {row["title"]}',
                f'{row["account_name"]} · Brak zapisu opłacenia za {occurrence}.',
                due.isoformat(), '/budget?' + urlencode({'view': 'bills', 'month': occurrence, 'bill': row['id']}),
                'Rozlicz rachunek', amount_cents(row,occurrence)/100))
            break

    paid_loans = {(r['loan_id'], r['installment_month']) for r in db.execute('SELECT loan_id, installment_month FROM loan_installment_payments')}
    for loan in db.execute('''SELECT id, name, original_amount, duration_months,
            CAST(start_date AS TEXT) AS start_date, installment_type, category FROM loans'''):
        try:
            schedule, _, _ = LoanService.calculate_schedule(dict(loan),
                LoanService.get_loan_rates(loan['id']), LoanService.get_loan_overpayments(loan['id']))
        except (ValueError, TypeError, IndexError, ZeroDivisionError):
            warnings.append(f'Nie udało się wyliczyć rat kredytu „{loan["name"]}”. Sprawdź jego harmonogram.')
            continue
        for row in schedule:
            if row['installment'] <= 0 or row.get('is_mid_month') or (loan['id'], row['month']) in paid_loans:
                continue
            if month + '-01' <= row['date'] <= horizon.isoformat():
                items.append(_action(f'loan:{loan["id"]}:{row["month"]}', 'loan', 'loans',
                    f'Sprawdź ratę: {loan["name"]}',
                    'Rata z harmonogramu. Brak zapisu płatności nie oznacza zaległości w banku.',
                    row['date'], f'/loans/{loan["id"]}?installment={row["month"]}', 'Sprawdź i zapisz spłatę',
                    round(row['installment'], 2)))

    for row in db.execute('''SELECT s.id, s.source_file, s.portfolio_id, p.name, COUNT(r.id) AS pending
            FROM import_sessions s JOIN portfolios p ON p.id=s.portfolio_id
            JOIN import_staging r ON r.import_session_id=s.id AND r.status IN ('pending','assigned')
            WHERE s.closed_at IS NULL AND p.is_archived=0 GROUP BY s.id'''):
        items.append(_action(f'import:{row["id"]}', 'import', 'investments',
            f'Dokończ import: {row["name"]}',
            f'{row["pending"]} transakcji do sprawdzenia · {row["source_file"] or "Zapisana sesja"}',
            href='/admin/portfolio/' + str(row['portfolio_id']) + '?' + urlencode({'import_session': row['id']}),
            action_label='Wznów import'))

    for row in db.execute('SELECT id, name, target_date FROM investment_goals WHERE is_archived=0 AND target_date<=?', (horizon.isoformat(),)):
        items.append(_action(f'goal:{row["id"]}', 'goal', 'investments',
            f'Oceń realizację celu: {row["name"]}', 'Zbliża się lub minął termin celu. Sprawdź postęp i dalszy plan.',
            row['target_date'], f'/goals?goal={row["id"]}', 'Sprawdź cel'))

    from budget_reserves_service import workspace as reserve_workspace
    for row in reserve_workspace()['items']:
        if row['status']!='ACTIVE':
            continue
        if row.get('monthly_amount') is not None:
            if not row.get('open_ended') and not db.execute('SELECT 1 FROM budget_reserve_month_plans WHERE reserve_id=? AND month=?',(row['id'],month)).fetchone():
                items.append(_action(f'media-review:{row["id"]}:{month}', 'reserve', 'budget',
                    f'Sprawdź kwotę mediów: {row["name"]}',
                    'Potwierdź bieżącą kwotę według licznika lub rozliczenia. Do tego czasu obowiązuje kwota domyślna.',
                    today.isoformat(), f'/budget?view=plan&month={month}&reserve={row["id"]}', 'Sprawdź plan miesiąca'))
            if row['remaining']>0:
                items.append(_action(f'reserve:{row["id"]}', 'reserve', 'budget',
                    f'Odłóż na rezerwę: {row["name"]}' if row.get('open_ended') else f'Uzupełnij miesięczną pulę: {row["name"]}',
                    f'Jeszcze {row["remaining"]:.2f} PLN ze stałego planu w tym miesiącu. Kwota na kolejne miesiące się nie zmienia.' if row.get('open_ended') else f'Jeszcze {row["remaining"]:.2f} PLN w bieżącym miesiącu. Możesz skorygować plan według licznika lub rozliczenia.',
                    today.isoformat(), '/budget?view=plan', 'Sprawdź pulę',row['remaining']))
            continue
        if row['remaining']>0:
            due = row['due_date'] if row['urgent'] else row['next_contribution_date']
            if due and due<=horizon.isoformat():
                items.append(_action(f'reserve:{row["id"]}', 'reserve', 'budget',
                    f'Odłóż na: {row["name"]}',
                    f'Pozostało {row["remaining"]:.2f} PLN do {row["due_date"]}. Kwota jest przeliczana po każdym odłożeniu.',
                    due, f'/budget/reserves?reserve={row["id"]}', 'Sprawdź rezerwę', row['monthly_required']))
        elif row['due_date']<=horizon.isoformat():
            items.append(_action(f'reserve:{row["id"]}', 'reserve', 'budget',
                f'Sprawdź płatność: {row["name"]}', 'Kwota jest odłożona. Zapisz płatność po jej wykonaniu.',
                row['due_date'], f'/budget/reserves?reserve={row["id"]}', 'Otwórz rezerwę', row['target_amount']))

    if db.execute('SELECT COUNT(*) FROM budget_accounts').fetchone()[0]:
        try:totals = monthly_budget_totals(db, month)
        except (ValueError,TypeError):
            if not warnings:
                warnings.append('Nie udało się ocenić planu budżetu. Sprawdź dane zobowiązań; pozostałe sprawy pozostają dostępne.')
            totals=None
        if totals and totals['to_plan'] < -.005:
            items.append(_action(f'budget-plan:{month}', 'budget_plan', 'budget', 'Skoryguj plan wydatków',
                'Plan przekracza środki po uwzględnieniu oczekiwanych wpływów tego miesiąca. Sprawdź kategorie, rachunki i dochody.',
                href=f'/budget?view=plan&month={month}', action_label='Popraw plan',
                amount=abs(totals['to_plan']), priority='high'))
        elif totals and totals['to_plan'] > .005:
            items.append(_action(f'budget-plan:{month}', 'budget_plan', 'budget', 'Rozdziel środki w budżecie',
                'Ta kwota pozostaje do zaplanowania po uwzględnieniu oczekiwanych wpływów bieżącego miesiąca.',
                href=f'/budget?view=plan&month={month}', action_label='Zaplanuj środki', amount=totals['to_plan']))

    completed = []
    for row in db.execute('SELECT * FROM dashboard_tasks ORDER BY id DESC'):
        item = _action(f'manual:{row["id"]}', 'manual', row['category'], row['title'], row['notes'],
                       row['due_date'], priority=row['priority'], task_id=row['id'], version=row['version'],
                       completed_at=row['completed_at'])
        (completed if row['completed_at'] else items).append(item)

    for item in items:
        due = item['due_date']
        item['timing'] = 'overdue' if due and due < today.isoformat() else 'today' if due == today.isoformat() else 'upcoming' if due else 'unscheduled'
    items.sort(key=lambda r: ({'overdue': 0, 'today': 1}.get(r['timing'], 2),
                              0 if r['priority'] == 'high' else 1, r['due_date'] or '9999', r['key']))
    completed.sort(key=lambda r: (r['completed_at'], r['task_id']), reverse=True)
    return dict(as_of=today.isoformat(), horizon=horizon.isoformat(), items=items, completed=completed,
                stats=dict(open=len(items), overdue=sum(r['timing']=='overdue' for r in items),
                           today=sum(r['timing']=='today' for r in items),
                           week=sum(bool(r['due_date']) and today.isoformat()<=r['due_date']<=(today+timedelta(days=7)).isoformat() for r in items),
                           completed=len(completed)), warnings=warnings)


def _validate(data):
    if not isinstance(data, dict):
        raise ValidationError('Nieprawidłowe dane zadania.')
    title, notes = data.get('title'), data.get('notes', '')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
        raise ValidationError('Tytuł musi mieć od 1 do 160 znaków.')
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValidationError('Opis może mieć najwyżej 2000 znaków.')
    category, priority, due = data.get('category', 'other'), data.get('priority', 'normal'), data.get('due_date')
    if category not in CATEGORIES or priority not in ('normal', 'high'):
        raise ValidationError('Nieprawidłowa kategoria lub priorytet.')
    if due is not None:
        try:
            parsed = date.fromisoformat(due)
            if parsed.isoformat() != due or not date(2000, 1, 1) <= parsed <= date(date.today().year+10, 12, 31):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError('Podaj poprawny termin zadania.')
    return title.strip(), notes.strip(), category, due, priority


def save_task(data, task_id=None):
    fields = _validate(data)
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute('BEGIN IMMEDIATE')
        if task_id is None:
            request_id = data.get('request_id')
            try:
                if not isinstance(request_id, str) or str(UUID(request_id)) != request_id:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError('Nieprawidłowy identyfikator zapisu.')
            previous = db.execute('SELECT * FROM dashboard_tasks WHERE request_id=?', (request_id,)).fetchone()
            if previous:
                # A retried POST never inserts another task, even if the first response was lost.
                original = tuple(previous[key] for key in ('title', 'notes', 'category', 'due_date', 'priority'))
                if original != fields:
                    raise ApiError('task_request_conflict', 'Poprzedni zapis został już przyjęty. Odśwież listę i edytuj zapisane zadanie.', status=409)
                return dict(id=previous['id'])
            task_id = db.execute('''INSERT INTO dashboard_tasks
                (title, notes, category, due_date, priority, request_id, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)''', (*fields, request_id, now, now)).lastrowid
        else:
            _check_version(db, task_id, data)
            db.execute('''UPDATE dashboard_tasks SET title=?, notes=?, category=?, due_date=?, priority=?,
                       updated_at=?, version=version+1 WHERE id=?''', (*fields, now, task_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction:
            db.rollback()
    return dict(id=task_id)


def _check_version(db, task_id, data):
    row = db.execute('SELECT * FROM dashboard_tasks WHERE id=?', (task_id,)).fetchone()
    if not row:
        raise NotFoundError('Zadanie nie istnieje.')
    if type(data.get('version')) is not int or data['version'] != row['version']:
        raise ApiError('task_conflict', 'Zadanie zmieniło się w innej karcie. Odśwież listę przed kolejną zmianą.', status=409)
    return row


def complete_task(task_id, data):
    if not isinstance(data, dict) or type(data.get('completed')) is not bool:
        raise ValidationError('Podaj stan wykonania zadania.')
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        row = _check_version(db, task_id, data)
        if bool(row['completed_at']) != data['completed']:
            now = datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE dashboard_tasks SET completed_at=?, updated_at=?, version=version+1 WHERE id=?',
                       (now if data['completed'] else None, now, task_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return dict(id=task_id)

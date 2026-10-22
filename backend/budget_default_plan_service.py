"""Shared month limits, dated defaults and reviewed, atomic range copies."""
import hashlib
import json
from datetime import date

from api.exceptions import ApiError, ValidationError


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def resolve(db, month, fallback_month=None):
    """Presence, including an explicit zero, decides precedence per category."""
    amounts, sources = {}, {}
    for row in db.execute('SELECT * FROM budget_default_plans WHERE start_month<=? ORDER BY start_month', (month,)):
        amounts[row['category_id']] = row['amount_cents']
        sources[row['category_id']] = dict(kind='DEFAULT', month=row['start_month'])
    for row in db.execute('SELECT * FROM budget_plans_v2 WHERE month=?', (month,)):
        amounts[row['category_id']] = row['amount_cents']
        sources[row['category_id']] = dict(kind='MONTH', month=month)
    if fallback_month and fallback_month != month:
        fallback, _ = resolve(db, fallback_month)
        parents={r['id']:r['parent_id'] for r in db.execute('SELECT id,parent_id FROM budget_categories_v2')}
        anchored=set(amounts)
        for category_id, amount in fallback.items():
            # A real shared cap already covers its unplanned children. An old
            # estimated child allowance must not silently raise that cap.
            if category_id not in amounts and parents.get(category_id) not in anchored:
                amounts[category_id] = amount
                sources[category_id] = dict(kind='ESTIMATE', month=fallback_month)
    return amounts, sources


def defaults(db, month):
    from budget_category_hierarchy_service import category_options
    history = {}
    for row in db.execute('SELECT * FROM budget_default_plans ORDER BY start_month'):
        history.setdefault(row['category_id'], []).append(dict(row))
    managed = {r[0] for r in db.execute('''SELECT category_id FROM budget_reserves WHERE is_archived=0
        AND completed_at IS NULL AND open_ended=0 AND monthly_amount_cents IS NOT NULL''')}
    result = []
    for category in category_options(db, include_unassigned=False):
        rows = history.get(category['id'], [])
        active = next((r for r in reversed(rows) if r['start_month'] <= month), None)
        result.append(dict(category_id=category['id'], name=category['path'], parent_id=category['parent_id'],
            managed=category['id'] in managed, amount=active['amount_cents']/100 if active else None,
            start_month=active['start_month'] if active else None, revision=fingerprint(rows),
            history=[dict(start_month=r['start_month'], amount=r['amount_cents']/100) for r in rows]))
    return dict(month=month, items=result)


def editable_month(db, month):
    from routes_budget_workspace import month_value
    month = month_value(month)
    if not date.today().strftime('%Y-%m') <= month <= '2100-12':
        raise ValidationError('Wybierz bieżący lub przyszły miesiąc, najpóźniej grudzień 2100.')
    if db.execute('SELECT 1 FROM budget_month_closings WHERE month>=?', (month,)).fetchone():
        raise ValidationError('Zacznij po ostatnim zamkniętym miesiącu, aby zachować zatwierdzone plany.')
    return month


def save_defaults(db, data):
    from routes_budget_workspace import positive_id, cents
    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 500 or any(not isinstance(r, dict) for r in items):
        raise ValidationError('Wybierz kategorie i ich domyślne limity.')
    db.execute('BEGIN IMMEDIATE')
    try:
        month = editable_month(db, data.get('start_month'))
        available = {r['category_id']: r for r in defaults(db, month)['items']}
        seen = set()
        for item in items:
            category_id = positive_id(item.get('category_id'), 'Kategoria')
            current = available.get(category_id)
            if not current or current['managed'] or category_id in seen:
                raise ValidationError('Wybierz różne kategorie, które nie są zarządzane przez miesięczne pule.')
            if item.get('revision') != current['revision']:
                raise ApiError('conflict', 'Plan domyślny zmienił się. Odśwież dane przed zapisem.', status=409)
            amount = cents(item.get('amount'), 'Limit domyślny', allow_zero=True)
            db.execute('''INSERT INTO budget_default_plans(category_id,start_month,amount_cents) VALUES(?,?,?)
                ON CONFLICT(category_id,start_month) DO UPDATE SET amount_cents=excluded.amount_cents,version=version+1''',
                (category_id, month, amount))
            seen.add(category_id)
        db.commit()
        return dict(saved=len(seen), start_month=month)
    except Exception:
        db.rollback()
        raise


def copy_preview(db, data):
    from routes_budget_workspace import month_value, positive_id
    from budget_category_hierarchy_service import category_options
    from budget_planning_service import shift_month
    source = month_value(data.get('source'))
    start = editable_month(db, data.get('start'))
    count = data.get('months')
    if type(count) is not int or count not in (3, 6, 12):
        raise ValidationError('Wybierz 3, 6 lub 12 miesięcy.')
    replace = data.get('replace', False)
    if type(replace) is not bool:
        raise ValidationError('Wybierz sposób uzupełniania istniejących limitów.')
    selected = data.get('category_ids')
    if not isinstance(selected, list) or not 1 <= len(selected) <= 500:
        raise ValidationError('Wybierz kategorie do skopiowania.')
    ids = [positive_id(value, 'Kategoria') for value in selected]
    if len(ids) != len(set(ids)):
        raise ValidationError('Kategorie nie mogą się powtarzać.')
    categories = {c['id']: c for c in category_options(db, include_unassigned=False)}
    if any(category_id not in categories for category_id in ids):
        raise ValidationError('Nieprawidłowa kategoria.')
    targets = [shift_month(start, i) for i in range(count)]
    if source in targets or targets[-1] > '2100-12':
        raise ValidationError('Zakres docelowy nie może zawierać miesiąca źródłowego ani przekraczać 2100 roku.')
    amounts, _ = resolve(db, source)
    managed = {r[0] for r in db.execute('''SELECT category_id FROM budget_reserves WHERE is_archived=0
        AND completed_at IS NULL AND open_ended=0 AND monthly_amount_cents IS NOT NULL''')}
    rows = []
    for month in targets:
        existing = dict(db.execute('SELECT category_id,amount_cents FROM budget_plans_v2 WHERE month=?', (month,)))
        effective, provenance = resolve(db, month)
        for category_id in ids:
            if category_id in managed:
                action = 'MANAGED'
            elif category_id not in amounts:
                action = 'NO_SOURCE'
            elif category_id in existing and not replace:
                action = 'KEEP'
            else:
                action = 'REPLACE' if category_id in existing else 'ADD'
            rows.append(dict(month=month, category_id=category_id, name=categories[category_id]['path'], action=action,
                amount=amounts.get(category_id, 0)/100, previous=effective.get(category_id, 0)/100,
                previous_source=provenance.get(category_id)))
    return dict(source=source, start=start, months=count, replace=replace, rows=rows,
        copied=sum(r['action'] in ('ADD', 'REPLACE') for r in rows),
        skipped=sum(r['action'] not in ('ADD', 'REPLACE') for r in rows), token=fingerprint(rows))


def copy_range(db, data):
    from budget_reserves_service import _request_id
    request_id = _request_id(data)
    payload = fingerprint(data)
    db.execute('BEGIN IMMEDIATE')
    try:
        old = db.execute('SELECT * FROM budget_plan_copy_requests WHERE request_id=?', (request_id,)).fetchone()
        if old:
            if old['request_payload'] != payload:
                raise ApiError('conflict', 'Ta prośba dotyczyła innego kopiowania.', status=409)
            db.rollback()
            return json.loads(old['result_json'])
        preview = copy_preview(db, data)
        if data.get('token') != preview['token']:
            raise ApiError('conflict', 'Limity zmieniły się od podglądu. Sprawdź nowy podgląd przed zapisem.', status=409)
        for row in preview['rows']:
            if row['action'] in ('ADD', 'REPLACE'):
                db.execute('''INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,?,?)
                    ON CONFLICT(category_id,month) DO UPDATE SET amount_cents=excluded.amount_cents''',
                    (row['category_id'], row['month'], round(row['amount']*100)))
        result = dict(copied=preview['copied'], skipped=preview['skipped'])
        db.execute('INSERT INTO budget_plan_copy_requests VALUES(?,?,?)', (request_id, payload, json.dumps(result)))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise

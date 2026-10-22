"""Read-only annual plans and reviewed moves of existing category allowances."""
import json

from api.exceptions import ApiError, ValidationError
from budget_default_plan_service import editable_month, fingerprint
from budget_category_hierarchy_service import category_workspace, plan_amounts


def annual_plan(db, start):
    from routes_budget_workspace import month_value, workspace_data
    from budget_planning_service import shift_month
    start = month_value(start)
    if shift_month(start, 11) > '2100-12':
        raise ValidationError('Wybierz zakres kończący się najpóźniej w grudniu 2100.')
    rows = []
    for index in range(12):
        month = shift_month(start, index)
        data = workspace_data(db, month)
        parts = {r['kind']: r for r in data['planning']['month_plan']}
        totals = data['totals']
        roots = [c for c in data['categories'] if c['parent_id'] is None]
        rows.append(dict(month=month, income=totals['monthly_income_total'],
            ordinary=parts.get('DAILY', {}).get('planned', 0),
            payments=sum(parts.get(kind, {}).get('planned', 0) for kind in ('BILLS', 'LOANS', 'MEDIA')),
            reserves=parts.get('RESERVES', {}).get('planned', 0),
            cost=round(totals['monthly_income_cost'] + totals['monthly_income_remaining_plan'], 2),
            remaining=totals['monthly_income_to_plan'], spent=totals['spent'],
            carryover=round(sum(c['carryover'] for c in roots), 2),
            missing_plans=[c['path'] for c in roots if c['has_activity'] and not c['is_unassigned']
                and c['planned'] == 0 and c['plan_source'] == 'NONE'],
            sources=[dict(id=c['id'], name=c['path'], source=c['plan_source'], amount=c['planned'])
                for c in data['categories'] if c['has_activity'] and not c['is_unassigned']]))
    return dict(start=start, months=rows)


def transfer_preview(db, data):
    from routes_budget_workspace import positive_id, cents, workspace_data
    month = editable_month(db, data.get('month'))
    source_id = positive_id(data.get('source_id'), 'Kategoria źródłowa')
    target_id = positive_id(data.get('target_id'), 'Kategoria docelowa')
    amount = cents(data.get('amount'))
    workspace = workspace_data(db, month)
    categories = workspace['categories']
    indexed = {r['id']: r for r in categories}
    source, target = indexed.get(source_id), indexed.get(target_id)
    if not source or not target or source_id == target_id:
        raise ValidationError('Wybierz dwie różne kategorie.')
    if any(c['is_unassigned'] or c['monthly_reserve_managed'] for c in (source, target)):
        raise ValidationError('Wybierz kategorie poza miesięcznymi pulami mediów i zakupami do przypisania.')
    source_root, target_root = source['parent_id'] or source_id, target['parent_id'] or target_id
    same_family = source_root == target_root
    if same_family and (source_id == source_root or target_id == target_root):
        raise ValidationError('W obrębie wspólnego limitu wybierz dwie podkategorie. Kategoria główna już zawiera ich kwoty.')
    protected = (source,) if same_family else (source, indexed[source_root])
    if any(amount > round(c['plan_details']['ordinary_remaining'] * 100) for c in protected):
        raise ValidationError('Ta kwota jest już wykorzystana albo przeznaczona na płatności. Przenieś tylko pozostały limit zwykłych wydatków.')
    manual = {c['id']: round(c['manual_plan'] * 100) for c in categories}
    changes = {}
    adjustments = [(source, -amount), (target, amount)]
    if not same_family:
        for category, difference in ((source, -amount), (target, amount)):
            if category['parent_id']:
                adjustments.append((indexed[category['parent_id']], difference))
    for category, difference in adjustments:
        value = round((category['planned'] + category['reserve_covered'] - category['carryover']) * 100) + difference
        if value < 0:
            raise ValidationError('Nie można przenieść kwoty pochodzącej wyłącznie z wcześniejszego limitu.')
        changes[category['id']] = value
    manual.update(changes)
    gross_bills = {}
    for category in categories:
        child_coverage = sum(c['reserve_covered'] for c in categories if c['parent_id'] == category['id'])
        direct_coverage = category['reserve_covered'] - child_coverage
        gross_bills[category['id']] = round((category['direct_planned_bills'] + direct_coverage) * 100)
    simulated = plan_amounts(categories, manual, gross_bills)
    for category in categories:
        simulated[category['id']] = max(0, simulated[category['id']] - round(category['reserve_covered'] * 100)) + round(category['carryover'] * 100)
    before_roots = {root: round(indexed[root]['planned'] * 100) for root in (source_root, target_root)}
    root_shift = 0 if same_family else amount
    if simulated[source_root] != before_roots[source_root] - root_shift or simulated[target_root] != before_roots[target_root] + root_shift:
        raise ValidationError('Wolny limit jest rozdzielony między podkategorie lub pokrywa płatności. Wybierz konkretną podkategorię z wolnym limitem.')
    if simulated[source_id] != round(source['planned'] * 100) - amount or simulated[target_id] != round(target['planned'] * 100) + amount:
        raise ValidationError('Nie można przesunąć tej kwoty bez naruszenia planów podkategorii lub płatności.')
    token = fingerprint(dict(month=month, categories=categories))
    return dict(month=month, source_id=source_id, target_id=target_id, amount=amount / 100,
        source_name=source['path'], target_name=target['path'], token=token,
        source_before=source['planned'], source_after=simulated[source_id]/100,
        target_before=target['planned'], target_after=simulated[target_id]/100,
        source_limit=changes[source_id]/100, target_limit=changes[target_id]/100,
        updates=[dict(category_id=category_id, amount=value/100, planned=simulated[category_id]/100)
                 for category_id, value in changes.items()],
        related_limits=[dict(name=indexed[root]['path'], before=indexed[root]['planned'], after=simulated[root]/100)
                        for root in dict.fromkeys((source_root, target_root)) if root not in (source_id, target_id)],
        total_before=round(sum(c['planned'] for c in categories if c['parent_id'] is None), 2),
        total_after=round(sum(simulated[c['id']] for c in categories if c['parent_id'] is None)/100, 2))


def transfer_plan(db, data):
    from routes_budget_workspace import text_field
    request_id = text_field(data.get('request_id'), 'Identyfikator zapisu', 100)
    payload = json.dumps({k: data.get(k) for k in ('month', 'source_id', 'target_id', 'amount', 'token')}, sort_keys=True)
    db.execute('BEGIN IMMEDIATE')
    try:
        previous = db.execute('SELECT * FROM budget_plan_transfer_requests WHERE request_id=?', (request_id,)).fetchone()
        if previous:
            if previous['payload'] != payload:
                raise ApiError('conflict', 'Ten zapis dotyczy innej zmiany limitów.', status=409)
            result = json.loads(previous['result'])
            db.rollback()
            return result
        preview = transfer_preview(db, data)
        if data.get('token') != preview['token']:
            raise ApiError('conflict', 'Plan lub wydatki zmieniły się. Sprawdź nowy podgląd.', status=409)
        for update in preview['updates']:
            db.execute('''INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,?,?)
                ON CONFLICT(category_id,month) DO UPDATE SET amount_cents=excluded.amount_cents''',
                (update['category_id'], preview['month'], round(update['amount']*100)))
        after = {c['id']: c for c in category_workspace(db, preview['month'])}
        if any(abs(after[update['category_id']]['planned'] - update['planned']) > .005 for update in preview['updates']):
            raise ValidationError('Nie można zachować podglądu przy aktualnych powiązaniach planu. Zmiana została wycofana.')
        result = {k: v for k, v in preview.items() if k != 'token'}
        db.execute('INSERT INTO budget_plan_transfer_requests VALUES(?,?,?)', (request_id, payload, json.dumps(result)))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise

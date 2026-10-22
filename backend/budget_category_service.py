"""Explicit category rules and category-only edits; these never move money."""
import json
from api.exceptions import ApiError, NotFoundError, ValidationError
from database import get_db
from budget_import_parser import normalized
from budget_reserves_service import _account, _fingerprint, _now, _request_id
from routes_budget_workspace import positive_id, text_field, validate_lines


def require_version(row, version, label='Dane'):
    if type(version) is not int or row['version'] != version:
        raise ApiError('budget_import_version_conflict', f'{label} zmieniły się. Odśwież dane przed zapisem.', status=409)


def category(db, category_id):
    category_id = positive_id(category_id, 'kategoria')
    row = db.execute('SELECT * FROM budget_categories_v2 WHERE id=?', (category_id,)).fetchone()
    if not row or row['is_unassigned']:
        raise ValidationError('Wybierz docelową kategorię wydatku.')
    return category_id


def unassigned_category(db):
    row = db.execute('SELECT id FROM budget_categories_v2 WHERE is_unassigned=1').fetchone()
    if row:
        return row['id']
    db.execute("INSERT OR IGNORE INTO budget_categories_v2 (name,icon,sort_order,is_unassigned) VALUES ('Nieprzypisane','CircleHelp',9999,1)")
    db.execute("UPDATE budget_categories_v2 SET is_unassigned=1 WHERE name='Nieprzypisane' COLLATE NOCASE")
    return db.execute('SELECT id FROM budget_categories_v2 WHERE is_unassigned=1').fetchone()[0]


def rules(db):
    from budget_category_hierarchy_service import category_options
    labels = {c['id']: c['selection_label'] for c in category_options(db)}
    return [{**dict(r), 'category_name': labels[r['category_id']]} for r in db.execute('''SELECT r.*,c.name category_name,a.name account_name
        FROM budget_category_rules r JOIN budget_categories_v2 c ON c.id=r.category_id
        LEFT JOIN budget_accounts a ON a.id=r.account_id ORDER BY r.priority DESC,r.id''')]


def rule_match(all_rules, account_id, merchant, description):
    matches = []
    for rule in all_rules:
        if not rule['active'] or rule['account_id'] not in (None, account_id):
            continue
        pattern = normalized(rule['pattern'])
        fields = [merchant, description] if rule['match_field'] == 'ANY' else [merchant if rule['match_field'] == 'MERCHANT' else description]
        values = [normalized(f) for f in fields]
        if any((pattern in value if rule['match_type'] == 'CONTAINS' else value.startswith(pattern)
                if rule['match_type'] == 'STARTS_WITH' else value == pattern) for value in values):
            matches.append(rule)
    if not matches:
        return None, []
    # Priority is explicit; a longer pattern is more specific. Ties with different
    # destinations remain unassigned instead of depending on insertion order.
    best_rank = max((r['priority'], len(normalized(r['pattern']))) for r in matches)
    best = [r for r in matches if (r['priority'], len(normalized(r['pattern']))) == best_rank]
    if len({r['category_id'] for r in best}) > 1:
        return None, ['Pasuje kilka reguł o tym samym priorytecie do różnych kategorii. Wybierz kategorię lub popraw reguły.']
    return best[0], []


def save_rule(data, rule_id=None):
    db, now = get_db(), _now()
    pattern = text_field(data.get('pattern'), 'Tekst reguły', 150)
    if len(normalized(pattern)) < 2:
        raise ValidationError('Tekst reguły musi zawierać przynajmniej dwa znaki lub cyfry.')
    match_field, match_type = data.get('match_field', 'ANY'), data.get('match_type', 'CONTAINS')
    if match_field not in ('ANY', 'MERCHANT', 'DESCRIPTION') or match_type not in ('CONTAINS', 'EQUALS', 'STARTS_WITH'):
        raise ValidationError('Nieprawidłowy sposób dopasowania reguły.')
    priority, active = data.get('priority', 100), data.get('active', True)
    if type(priority) is not int or not 0 <= priority <= 10000 or type(active) is not bool:
        raise ValidationError('Priorytet musi być liczbą od 0 do 10000, a stan reguły wartością logiczną.')
    account_id = positive_id(data['account_id'], 'konto') if data.get('account_id') is not None else None
    try:
        db.execute('BEGIN IMMEDIATE')
        if rule_id is None:
            token, fingerprint = _request_id(data), _fingerprint(data)
            previous = db.execute('SELECT * FROM budget_category_rules WHERE request_id=?', (token,)).fetchone()
            if previous:
                if previous['request_payload'] != fingerprint:
                    raise ApiError('rule_request_conflict', 'Ten zapis reguły przyjęto z innymi danymi.', status=409)
                return dict(id=previous['id'])
        else:
            row = db.execute('SELECT * FROM budget_category_rules WHERE id=?', (rule_id,)).fetchone()
            if not row:
                raise NotFoundError('Reguła nie istnieje.')
            require_version(row, data.get('version'), 'Reguły')
        if account_id is not None:
            _account(db, account_id)
        if data.get('new_category'):
            name = text_field(data['new_category'], 'Nowa kategoria', 100)
            existing = db.execute('SELECT id FROM budget_categories_v2 WHERE name=? COLLATE NOCASE', (name,)).fetchone()
            target_id = existing['id'] if existing else db.execute('INSERT INTO budget_categories_v2 (name,sort_order) VALUES (?,100)', (name,)).lastrowid
            category_id = category(db, target_id)
        else:
            category_id = category(db, data.get('category_id'))
        name = text_field(data.get('name') or pattern, 'Nazwa reguły', 150)
        values = (name, pattern, match_field, match_type, category_id, account_id, priority, int(active))
        if rule_id is None:
            for existing in db.execute('SELECT * FROM budget_category_rules WHERE account_id IS ? AND match_field=? AND match_type=?', (account_id,match_field,match_type)):
                if normalized(existing['pattern'])==normalized(pattern) and existing['active'] and active and existing['category_id']==category_id and existing['priority']==priority:
                    db.commit()
                    return dict(id=existing['id'])
            rule_id = db.execute('''INSERT INTO budget_category_rules
                (name,pattern,match_field,match_type,category_id,account_id,priority,active,request_id,request_payload,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (*values, token, fingerprint, now, now)).lastrowid
        else:
            db.execute('''UPDATE budget_category_rules SET name=?,pattern=?,match_field=?,match_type=?,category_id=?,account_id=?,
                priority=?,active=?,version=version+1,updated_at=? WHERE id=?''', (*values, now, rule_id))
        db.commit()
        return dict(id=rule_id)
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction:
            db.rollback()


def set_lines(db, entry, category_id=None, lines=None):
    if lines is not None:
        validated = validate_lines(dict(lines=lines), 'EXPENSE', entry['amount_cents'])
        for line in validated:
            category(db, line['category_id'])
        status = 'SPLIT'
    else:
        target = category(db, category_id) if category_id is not None else unassigned_category(db)
        validated = [dict(category_id=target, label='', amount_cents=entry['amount_cents'])]
        status = 'GENERAL' if category_id is not None else 'UNASSIGNED'
    monthly=db.execute('''SELECT r.category_id FROM budget_reserve_movements m JOIN budget_reserves r ON r.id=m.reserve_id
        WHERE m.budget_entry_id=? AND r.monthly_amount_cents IS NOT NULL AND r.open_ended=0''',(entry['id'],)).fetchone()
    if monthly and any(line['category_id']!=monthly['category_id'] for line in validated):
        raise ValidationError('Płatność rozlicza miesięczną pulę. Zachowaj kategorię tej puli.')
    bill=db.execute('''SELECT b.category_id FROM budget_bill_payments_v2 p
        JOIN budget_bills_v2 b ON b.id=p.bill_id WHERE p.entry_id=?''',(entry['id'],)).fetchone()
    if bill and any(line['category_id']!=bill['category_id'] for line in validated):
        raise ValidationError('Wydatek rozlicza rachunek. Najpierw cofnij jego rozliczenie, zanim zmienisz kategorię płatności.')
    if db.execute('SELECT 1 FROM loan_installment_payments WHERE budget_entry_id=?',(entry['id'],)).fetchone():
        raise ValidationError('Wydatek rozlicza ratę kredytu. Najpierw cofnij powiązanie w kredycie, zanim zmienisz kategorię płatności.')
    db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id=?', (entry['id'],))
    for line in validated:
        db.execute('INSERT INTO budget_entry_lines_v2 (entry_id,category_id,label,amount_cents) VALUES (?,?,?,?)',
                   (entry['id'], line['category_id'], line['label'], line['amount_cents']))
    db.execute('UPDATE budget_entries_v2 SET classification_status=?,version=version+1 WHERE id=?', (status, entry['id']))


def categorize(data):
    ids = data.get('entry_ids')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 500:
        raise ValidationError('Wybierz od 1 do 500 różnych wydatków.')
    ids = [positive_id(i, 'wydatek') for i in ids]
    if len(set(ids)) != len(ids):
        raise ValidationError('Wybierz różne wydatki.')
    versions = data.get('versions')
    if not isinstance(versions, dict):
        raise ValidationError('Odśwież wersje wydatków przed przypisaniem.')
    if data.get('lines') is not None and len(ids) != 1:
        raise ValidationError('Podział produktów dotyczy jednego wydatku.')
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        for entry_id in ids:
            row = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (entry_id,)).fetchone()
            if not row or row['kind'] != 'EXPENSE':
                raise ValidationError('Wybierz istniejące wydatki.')
            require_version(row, versions.get(str(entry_id)), 'Wydatki')
            set_lines(db, row, data.get('category_id'), data.get('lines'))
        db.commit()
        return dict(updated=len(ids))
    except Exception:
        db.rollback()
        raise


def apply_rules(data):
    ids, versions = data.get('entry_ids'), data.get('versions')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 500 or not isinstance(versions, dict):
        raise ValidationError('Wybierz do 500 wydatków z aktualnymi wersjami.')
    ids = [positive_id(i, 'wydatek') for i in ids]
    if len(set(ids)) != len(ids):
        raise ValidationError('Wybierz różne wydatki.')
    db, assigned = get_db(), 0
    try:
        db.execute('BEGIN IMMEDIATE'); all_rules = rules(db)
        for entry_id in ids:
            row = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (entry_id,)).fetchone()
            if not row or row['kind'] != 'EXPENSE' or row['classification_status'] != 'UNASSIGNED':
                raise ValidationError('Reguły stosujemy tylko do nieprzypisanych wydatków. Odśwież listę.')
            require_version(row, versions.get(str(entry_id)), 'Wydatki')
            matched, _ = rule_match(all_rules, row['account_id'], row['merchant'], row['description'])
            if matched:
                set_lines(db, row, matched['category_id']); assigned += 1
        db.commit()
        return dict(updated=assigned, unmatched=len(ids)-assigned)
    except Exception:
        db.rollback()
        raise

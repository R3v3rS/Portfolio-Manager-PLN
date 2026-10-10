"""Review-first bank CSV imports. Booking is atomic and identity-protected."""
import hashlib
import json
from datetime import date, timedelta
from uuid import uuid4

from api.exceptions import ApiError, NotFoundError, ValidationError
from database import get_db
from budget_import_parser import guessed_mapping, normalized, parse_bank_row, parsed_date, read_csv, validate_mapping
from budget_category_service import category, require_version, rule_match, rules, set_lines
from budget_reserves_service import _account, _fingerprint, _now, _request_id
from routes_budget_workspace import cents, insert_entry, positive_id, text_field
import budget_reserve_funding_service as funding
from budget_reserves_service import _row as reserve_row, reserved_cents


def merchant_matches(a, b):
    a, b = normalized(a), normalized(b)
    return bool(a and b and (a == b or (len(a) >= 3 and a in b) or (len(b) >= 3 and b in a)))


def entry_view(db, row, merchant=''):
    from budget_category_hierarchy_service import category_options
    labels = {c['id']: c['selection_label'] for c in category_options(db)}
    lines = [dict(r) for r in db.execute('''SELECT l.category_id,l.label,l.amount_cents/100.0 amount,c.name category_name
        FROM budget_entry_lines_v2 l JOIN budget_categories_v2 c ON c.id=l.category_id WHERE l.entry_id=? ORDER BY l.id''', (row['id'],))]
    lines = [{**line, 'category_name': labels[line['category_id']]} for line in lines]
    return dict(id=row['id'], account_id=row['account_id'], account_name=row['account_name'], date=row['date'],
                amount=row['amount_cents']/100, description=row['description'], merchant=row['merchant'],
                version=row['version'], classification_status=row['classification_status'], has_receipt=bool(row['receipt_filename']),
                merchant_match=merchant_matches(merchant, row['merchant'] or row['description']), lines=lines)


def entries_matching(db, account_id, day, amount_cents, kind='EXPENSE', merchant='', window=0):
    if not day or not amount_cents:
        return []
    anchor = date.fromisoformat(day)
    result = []
    for row in db.execute('''SELECT e.*,a.name account_name FROM budget_entries_v2 e JOIN budget_accounts a ON a.id=e.account_id
        WHERE e.kind=? AND e.amount_cents=? AND e.date BETWEEN ? AND ? AND (? IS NULL OR e.account_id=?)
        AND UPPER(COALESCE(a.currency,'PLN'))='PLN' ORDER BY ABS(julianday(e.date)-julianday(?)),e.id DESC LIMIT 100''',
        (kind, amount_cents, (anchor-timedelta(days=window)).isoformat(), (anchor+timedelta(days=window)).isoformat(), account_id, account_id, day)):
        result.append(entry_view(db, row, merchant))
    return sorted(result, key=lambda e: not e['merchant_match'])


def source_row(db, account_id, identity):
    return db.execute('SELECT * FROM budget_import_sources WHERE account_id=? AND source_identity=?', (account_id, identity)).fetchone()


def compatible_entry(entry, account_id, item):
    return bool(entry and (entry['account_id'],entry['kind'],entry['amount_cents']) ==
                (account_id,item['bank_kind'],item['amount_cents']) and
                abs((date.fromisoformat(entry['date'])-date.fromisoformat(item['date'])).days) <= 3)


def transfer_candidates(db, account_id, item):
    if item['errors']:
        return []
    return [dict(t) for t in db.execute('''SELECT t.*,s.name source_name,a.name target_name,t.amount_cents/100.0 amount
        FROM budget_account_transfers t JOIN budget_accounts s ON s.id=t.source_account_id
        JOIN budget_accounts a ON a.id=t.target_account_id
        WHERE t.move_money=1 AND t.amount_cents=? AND ABS(julianday(t.date)-julianday(?))<=3 AND
        ((?='EXPENSE' AND t.source_account_id=?) OR (?='INCOME' AND t.target_account_id=?))
        ORDER BY ABS(julianday(t.date)-julianday(?)),t.id DESC''',
        (item['amount_cents'],item['date'],item['bank_kind'],account_id,item['bank_kind'],account_id,item['date']))]


def transfer_proposal(db, account_id, item):
    matched, warnings = funding.match_rules(db, account_id, item)
    item['warnings'].extend(warnings)
    if warnings:
        item['kind']='TRANSFER'
        item.update(reserve_id=None,reserve_version=None,target_account_id=None,target_balance=None,transfer_rule_name=None)
        return 'SKIP', None
    if not matched:
        return None, None
    other_id = matched['target_account_id'] if item['bank_kind']=='EXPENSE' else matched['source_account_id']
    reserve = reserve_row(db, matched['reserve_id'])
    item.update(kind='TRANSFER',target_account_id=other_id,target_balance=float(_account(db,other_id)['balance']),
                reserve_id=reserve['id'],reserve_version=reserve['version'],transfer_rule_name=matched['pattern'])
    candidates = [t for t in transfer_candidates(db,account_id,item)
                  if (t['source_account_id'],t['target_account_id'],t['reserve_id']) ==
                  (matched['source_account_id'],matched['target_account_id'],matched['reserve_id'])
                  and not db.execute('SELECT 1 FROM budget_import_sources WHERE account_id=? AND transfer_id=?', (account_id,t['id'])).fetchone()]
    if len(candidates)==1:
        item['warnings'].append('Reguła rezerwy: proponujemy powiązanie z zapisanym przelewem. Salda i rezerwa nie zmienią się ponownie.')
        return 'MATCH', candidates[0]['id']
    if candidates:
        item['warnings'].append('Kilka podobnych przelewów na tę rezerwę. Wybierz właściwe powiązanie.')
        return 'SKIP', None
    item['warnings'].append('Reguła rezerwy: przelew własny i nowe odłożenie obciążające budżet miesiąca. Sprawdź opis i oba konta.')
    return 'NEW', None


def preview(content, header_index=None):
    data = read_csv(content, header_index)
    stored = get_db().execute('SELECT mapping_json FROM budget_csv_profiles WHERE signature=?', (data['signature'],)).fetchone()
    mapping = json.loads(stored[0]) if stored else guessed_mapping(data['headers'])
    return dict(columns=data['headers'], sample=data['rows'][:8], count=len(data['rows']), header_index=data['header_index'],
                encoding=data['encoding'], delimiter=data['delimiter'], mapping=mapping, remembered=bool(stored))


def session_row(db, session_id):
    row = db.execute('SELECT * FROM budget_import_sessions WHERE id=?', (session_id,)).fetchone()
    if not row:
        raise NotFoundError('Import nie istnieje.')
    return row


def stage(content, filename, data):
    parsed = read_csv(content, data.get('header_index'))
    mapping = validate_mapping(data.get('mapping'), len(parsed['headers']))
    account_id = positive_id(data.get('account_id'), 'konto')
    mode = data.get('balance_mode', 'HISTORY')
    if mode not in ('HISTORY', 'APPLY'):
        raise ValidationError('Wybierz historię bez zmiany salda albo nowe operacje.')
    token = _request_id(data)
    file_hash = hashlib.sha256(content).hexdigest()
    fingerprint = _fingerprint(dict(account_id=account_id, file_hash=file_hash, mapping=mapping, balance_mode=mode,
                                   header_index=parsed['header_index']))
    db, now = get_db(), _now()
    try:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT * FROM budget_import_sessions WHERE request_id=?', (token,)).fetchone()
        if prior:
            if prior['request_payload'] != fingerprint:
                raise ApiError('import_request_conflict', 'Ten import przyjęto z innymi danymi.', status=409)
            return dict(id=prior['id'])
        account = _account(db, account_id)
        session_id = db.execute('''INSERT INTO budget_import_sessions
            (account_id,filename,file_hash,balance_mode,expected_balance_cents,request_id,request_payload,created_at)
            VALUES (?,?,?,?,?,?,?,?)''', (account_id, text_field(filename or 'wyciag.csv', 'Nazwa pliku', 150), file_hash, mode,
                                        round(float(account['balance'])*100), token, fingerprint, now)).lastrowid
        all_rules, used_entries, used_identities = rules(db), set(), set()
        for index, cells in enumerate(parsed['rows'], 1):
            item = parse_bank_row(cells, mapping, len(parsed['headers']))
            item['bank_kind'] = item['kind']
            item['raw'] = [c[:2000] for c in cells]
            identity = 'bank:'+item['reference'] if item['reference'] else f'file:{file_hash}:{index}'
            action, entry_id, transfer_id = 'NEW', None, None
            previous = source_row(db, account_id, identity)
            if previous:
                action, entry_id = 'SKIP', previous['entry_id']
                item['warnings'].append('Ta operacja była już importowana. Ponowne księgowanie jest zablokowane.')
                if (previous['amount_cents'], previous['date'], previous['kind']) != (item['amount_cents'], item['date'], item['kind']):
                    item['warnings'].append('Identyfikator bankowy ma inne dane niż poprzedni import. Sprawdź plik źródłowy.')
            elif identity in used_identities:
                action = 'SKIP'
                item['warnings'].append('Identyfikator operacji powtarza się wewnątrz pliku.')
            elif not item['errors']:
                candidates = [e for e in entries_matching(db, account_id, item['date'], item['amount_cents'], item['kind'], item['merchant'] or item['description'], window=3) if e['id'] not in used_entries]
                strong = [e for e in candidates if e['merchant_match']]
                if len(strong) == 1:
                    entry_id, action = strong[0]['id'], 'MATCH'
                    item['entry_version'] = strong[0]['version']
                    used_entries.add(entry_id)
                    item['warnings'].append('Proponujemy połączenie z istniejącym wpisem. Sprawdź, czy to ten sam zakup.')
                elif candidates:
                    action = 'SKIP'
                    item['warnings'].append('Istnieją podobne wpisy. Wybierz połączenie lub świadomie zapisz jako odrębny zakup.')
                matched, warnings = rule_match(all_rules, account_id, item['merchant'], item['description'])
                item['warnings'].extend(warnings)
                if matched and item['kind'] == 'EXPENSE':
                    item.update(category_id=matched['category_id'], rule_id=matched['id'], rule_name=matched['name'])
                if item['transfer_hint']:
                    action = 'SKIP'
                    item['warnings'].append('Opis sugeruje przelew własny. Wskaż drugie konto lub pomiń wpis już zapisany w przelewach.')
                proposed, proposed_id = transfer_proposal(db,account_id,item)
                if proposed:
                    action,entry_id,transfer_id=proposed,None,proposed_id
            used_identities.add(identity)
            db.execute('''INSERT INTO budget_import_rows (session_id,row_number,source_identity,data_json,action,entry_id,transfer_id)
                VALUES (?,?,?,?,?,?,?)''', (session_id, index, identity, json.dumps(item, ensure_ascii=False), action, entry_id,transfer_id))
        db.execute('''INSERT INTO budget_csv_profiles (signature,mapping_json,updated_at) VALUES (?,?,?)
            ON CONFLICT(signature) DO UPDATE SET mapping_json=excluded.mapping_json,updated_at=excluded.updated_at''',
            (parsed['signature'], json.dumps({k: str(v) if v is not None else '' for k, v in mapping.items()}), now))
        db.commit()
        return dict(id=session_id)
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction:
            db.rollback()


def view(session_id):
    db = get_db()
    session = dict(session_row(db, session_id))
    account = _account(db, session['account_id'])
    result_rows, delta = [], 0
    for row in db.execute('SELECT * FROM budget_import_rows WHERE session_id=? ORDER BY row_number', (session_id,)):
        item = json.loads(row['data_json'])
        candidates = entries_matching(db, session['account_id'], item['date'], item['amount_cents'], item.get('bank_kind', item['kind']), item['merchant'] or item['description'], window=3) if not item['errors'] else []
        transfers = transfer_candidates(db,session['account_id'],item)
        if row['action'] == 'NEW' and not item['errors'] and item['kind'] != 'TRANSFER':
            delta += item['amount_cents'] * (1 if item['kind'] == 'INCOME' else -1)
        if row['action'] == 'NEW' and not item['errors'] and item['kind'] == 'TRANSFER':
            delta += item['amount_cents'] * (1 if item['bank_kind'] == 'INCOME' else -1)
        result_rows.append(dict(id=row['id'], row_number=row['row_number'], action=row['action'], entry_id=row['entry_id'],
            transfer_id=row['transfer_id'], manual_category=bool(row['manual_category']), **item,
            amount=item['amount_cents']/100, candidates=candidates, transfer_candidates=transfers,
            source_exists=bool(source_row(db, session['account_id'], row['source_identity']))))
    delta = delta if session['balance_mode'] == 'APPLY' else 0
    return dict(id=session_id, account_id=session['account_id'], account_name=account['name'], filename=session['filename'],
                balance_mode=session['balance_mode'], status=session['status'], version=session['version'],
                opening_balance=float(account['balance']), expected_balance=session['expected_balance_cents']/100,
                closing_balance=round(float(account['balance'])+delta/100, 2), cash_delta=delta/100,
                rows=result_rows, result=json.loads(session['result_json']) if session['result_json'] else None)


def update_row(session_id, row_id, data):
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        session = session_row(db, session_id)
        require_version(session, data.get('version'), 'Importy')
        if session['status'] != 'PENDING':
            raise ValidationError('Ten import został już zakończony.')
        row = db.execute('SELECT * FROM budget_import_rows WHERE id=? AND session_id=?', (row_id, session_id)).fetchone()
        if not row:
            raise NotFoundError('Wiersz nie istnieje.')
        item = json.loads(row['data_json'])
        action = data.get('action', row['action'])
        if action not in ('NEW', 'MATCH', 'SKIP'):
            raise ValidationError('Wybierz zapis, połączenie albo pominięcie.')
        if 'category_id' in data:
            item['category_id'] = category(db, data['category_id']) if data['category_id'] is not None else None
            item.pop('rule_id', None); item.pop('rule_name', None)
        if 'kind' in data:
            if data['kind'] not in (item['bank_kind'], 'TRANSFER'):
                raise ValidationError('Znak kwoty z banku określa wpływ lub wydatek. Możesz oznaczyć przelew własny.')
            item['kind'] = data['kind']
        if any(k in data for k in ('kind','target_account_id','reserve_id','action','transfer_id')):
            item['manual_transfer']=True
        if any(k in data for k in ('kind','target_account_id','reserve_id')):
            item['transfer_rule_name']=None
        if 'reserve_id' in data:
            reserve_id = positive_id(data['reserve_id'],'rezerwa') if data['reserve_id'] is not None else None
            if reserve_id and item['kind']!='TRANSFER':
                raise ValidationError('Odłożenie na rezerwę wymaga przelewu własnego.')
            reserve = reserve_row(db,reserve_id) if reserve_id else None
            if reserve and (reserve['is_archived'] or reserve['completed_at']):
                raise ValidationError('Rezerwa nie jest aktywna.')
            item.update(reserve_id=reserve_id,reserve_version=reserve['version'] if reserve else None)
        if item['kind']!='TRANSFER':
            item.update(reserve_id=None,reserve_version=None,transfer_rule_name=None)
        if 'target_account_id' in data:
            target = positive_id(data['target_account_id'], 'drugie konto') if data['target_account_id'] is not None else None
            if target == session['account_id']:
                raise ValidationError('Wybierz drugie konto.')
            item['target_account_id'] = target
            item['target_balance'] = float(_account(db, target)['balance']) if target else None
        entry_id = positive_id(data['entry_id'], 'wpis') if data.get('entry_id') is not None else row['entry_id']
        transfer_id = positive_id(data['transfer_id'], 'przelew') if data.get('transfer_id') is not None else row['transfer_id']
        if entry_id and item['kind'] != 'TRANSFER':
            existing = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (entry_id,)).fetchone()
            if not compatible_entry(existing,session['account_id'],item):
                raise ValidationError('Wpis musi mieć to samo konto, kierunek i kwotę, a datę w odstępie do 3 dni.')
            item['entry_version'] = existing['version']
        db.execute('UPDATE budget_import_rows SET action=?,entry_id=?,transfer_id=?,manual_category=?,data_json=? WHERE id=?',
                   (action, entry_id, transfer_id, int('category_id' in data or row['manual_category']), json.dumps(item, ensure_ascii=False), row_id))
        db.execute('UPDATE budget_import_sessions SET version=version+1 WHERE id=?', (session_id,))
        db.commit()
        return dict(id=session_id)
    except Exception:
        db.rollback()
        raise


def refresh(session_id, data):
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        session = session_row(db, session_id)
        require_version(session, data.get('version'), 'Importy')
        if session['status'] != 'PENDING':
            raise ValidationError('Ten import został już zakończony.')
        for row in db.execute('SELECT * FROM budget_import_rows WHERE session_id=?', (session_id,)).fetchall():
            item = json.loads(row['data_json'])
            if row['action'] == 'MATCH' and row['entry_id'] and item['kind'] != 'TRANSFER':
                existing = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (row['entry_id'],)).fetchone()
                if compatible_entry(existing, session['account_id'], item):
                    item['entry_version'] = existing['version']
            if not row['manual_category'] and item['kind'] == 'EXPENSE':
                matched, warnings = rule_match(rules(db), session['account_id'], item['merchant'], item['description'])
                item.update(category_id=matched['category_id'] if matched else None, rule_id=matched['id'] if matched else None,
                            rule_name=matched['name'] if matched else None)
                item['warnings'] = list(dict.fromkeys(item['warnings']+warnings))
            if not item.get('manual_transfer') and not item['errors'] and not source_row(db,session['account_id'],row['source_identity']):
                proposed, transfer_id = transfer_proposal(db,session['account_id'],item)
                if proposed:
                    db.execute('UPDATE budget_import_rows SET action=?,entry_id=NULL,transfer_id=? WHERE id=?', (proposed,transfer_id,row['id']))
                elif item.get('transfer_rule_name'):
                    item.update(reserve_id=None,reserve_version=None,target_account_id=None,target_balance=None,transfer_rule_name=None)
                    item['warnings'].append('Reguła przelewu została wstrzymana lub zmieniona. Wybierz ponownie konto i cel przed zapisem.')
                    db.execute("UPDATE budget_import_rows SET action='SKIP',transfer_id=NULL WHERE id=?", (row['id'],))
            if item.get('reserve_id'):
                item['reserve_version']=reserve_row(db,item['reserve_id'])['version']
            if item.get('target_account_id'):
                item['target_balance'] = float(_account(db, item['target_account_id'])['balance'])
            db.execute('UPDATE budget_import_rows SET data_json=? WHERE id=?', (json.dumps(item, ensure_ascii=False), row['id']))
        balance = round(float(_account(db, session['account_id'])['balance'])*100)
        db.execute('UPDATE budget_import_sessions SET expected_balance_cents=?,version=version+1 WHERE id=?', (balance, session_id))
        db.commit()
        return dict(id=session_id)
    except Exception:
        db.rollback()
        raise


def commit(session_id, data):
    token, fingerprint, db = _request_id(data), _fingerprint(dict(data, session_id=session_id)), get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        session = session_row(db, session_id)
        if session['commit_request_id']:
            if session['commit_request_id'] == token and session['commit_payload'] == fingerprint:
                return json.loads(session['result_json'])
            raise ApiError('import_closed', 'Import został już zatwierdzony. Odśwież jego wynik.', status=409)
        require_version(session, data.get('version'), 'Importy')
        account = _account(db, session['account_id'])
        effect = int(session['balance_mode'] == 'APPLY')
        if effect and round(float(account['balance'])*100) != session['expected_balance_cents']:
            raise ApiError('import_balance_conflict', 'Saldo konta zmieniło się. Odśwież saldo i sprawdź podsumowanie importu.', status=409)
        rows = db.execute('SELECT * FROM budget_import_rows WHERE session_id=? ORDER BY row_number', (session_id,)).fetchall()
        # Validate snapshots for every other account before any cash mutation.
        for row in rows:
            item = json.loads(row['data_json'])
            if row['action']=='NEW' and item['kind']=='TRANSFER' and item.get('reserve_id'):
                reserve = reserve_row(db,item['reserve_id'])
                require_version(reserve,item.get('reserve_version'),'Rezerwy')
            if row['action'] == 'NEW' and item['kind'] == 'TRANSFER' and effect:
                target = _account(db, item.get('target_account_id'))
                if float(target['balance']) != item.get('target_balance'):
                    raise ApiError('import_balance_conflict', 'Saldo drugiego konta zmieniło się. Odśwież import.', status=409)
        result = dict(created=0, linked=0, skipped=0, transfers=0)
        linked_entries, linked_transfers = set(), set()
        # Reserve history is chronological even when a bank exports newest first.
        for row in sorted(rows,key=lambda r: json.loads(r['data_json'])['date'] or ''):
            item = json.loads(row['data_json'])
            if row['action'] == 'SKIP':
                result['skipped'] += 1
                continue
            if item['errors']:
                raise ValidationError(f'Wiersz {row["row_number"]}: popraw mapowanie pliku albo pomiń błędny wiersz.')
            previous = source_row(db, session['account_id'], row['source_identity'])
            if previous:
                raise ApiError('bank_source_duplicate', f'Wiersz {row["row_number"]}: ta operacja była już importowana. Pomiń ją.', status=409)
            entry_id, transfer_id = None, None
            if item['kind'] == 'TRANSFER':
                original = item['bank_kind']
                if row['action'] == 'MATCH':
                    transfer = db.execute('SELECT * FROM budget_account_transfers WHERE id=?', (row['transfer_id'],)).fetchone()
                    expected_account = 'source_account_id' if original == 'EXPENSE' else 'target_account_id'
                    if not transfer or not transfer['move_money'] or (transfer[expected_account], transfer['amount_cents']) != (session['account_id'], item['amount_cents']) or abs((date.fromisoformat(transfer['date'])-date.fromisoformat(item['date'])).days)>3:
                        raise ValidationError('Wybierz zgodny istniejący przelew własny.')
                    transfer_id = transfer['id']; result['linked'] += 1
                    if transfer_id in linked_transfers:
                        raise ValidationError('Dwie operacje w tym imporcie nie mogą wskazywać tego samego przelewu.')
                    linked_transfers.add(transfer_id)
                else:
                    target = _account(db, item.get('target_account_id'))
                    if target['id'] == session['account_id']:
                        raise ValidationError('Przelew własny wymaga dwóch różnych kont.')
                    source_id, target_id = (session['account_id'], target['id']) if original == 'EXPENSE' else (target['id'], session['account_id'])
                    reserve_id = item.get('reserve_id')
                    reserve = reserve_row(db,reserve_id) if reserve_id else None
                    if reserve and effect:
                        source = _account(db,source_id)
                        if item['amount_cents']>max(0,round(float(source['balance'])*100)-reserved_cents(db,source_id)):
                            raise ValidationError('Przelew na rezerwę przekracza wolne środki na koncie źródłowym.')
                    if effect:
                        db.execute('UPDATE budget_accounts SET balance=ROUND(balance-?,2) WHERE id=?', (item['amount_cents']/100, source_id))
                        db.execute('UPDATE budget_accounts SET balance=ROUND(balance+?,2) WHERE id=?', (item['amount_cents']/100, target_id))
                    transfer_token = str(uuid4())
                    if reserve:
                        funding.fund(db,reserve_id,target_id,item['amount_cents'],item['date'],item['description'],transfer_token,history=not effect)
                    transfer_id = db.execute('''INSERT INTO budget_account_transfers
                        (source_account_id,target_account_id,move_money,cash_effect,amount_cents,date,notes,request_id,request_payload,created_at,reserve_id,cycle,reserve_action)
                        VALUES (?,?,1,?,?,?,?,?,?,?,?,?,?)''', (source_id, target_id, effect, item['amount_cents'], item['date'], item['description'],
                                                        transfer_token, '{}', _now(),reserve_id,reserve['cycle'] if reserve else None,'FUND' if reserve else 'MOVE')).lastrowid
                    result['transfers'] += 1
            elif row['action'] == 'MATCH':
                entry = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (row['entry_id'],)).fetchone()
                if not compatible_entry(entry,session['account_id'],item):
                    raise ValidationError('Połączenie wymaga zgodnego istniejącego wpisu.')
                require_version(entry, item.get('entry_version'), 'Powiązane wpisy')
                entry_id = entry['id']; result['linked'] += 1
                if entry_id in linked_entries:
                    raise ValidationError('Dwie operacje w tym imporcie nie mogą wskazywać tego samego zakupu.')
                linked_entries.add(entry_id)
            else:
                if item.get('category_id') is not None:
                    category(db, item['category_id'])
                entry_id = insert_entry(db, dict(account_id=session['account_id'], kind=item['bank_kind'], amount_cents=item['amount_cents'],
                    date=item['date'], description=item['description'], merchant=item['merchant'] or None, lines=[], cash_effect=effect))
                if item['bank_kind'] == 'EXPENSE':
                    set_lines(db, db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (entry_id,)).fetchone(), item.get('category_id'))
                result['created'] += 1
            db.execute('''INSERT INTO budget_import_sources (account_id,source_identity,entry_id,transfer_id,amount_cents,date,kind)
                VALUES (?,?,?,?,?,?,?)''', (session['account_id'], row['source_identity'], entry_id, transfer_id, item['amount_cents'], item['date'], item['bank_kind']))
            db.execute('UPDATE budget_import_rows SET entry_id=?,transfer_id=? WHERE id=?', (entry_id, transfer_id, row['id']))
        result.update(balance=float(_account(db, session['account_id'])['balance']), balance_mode=session['balance_mode'])
        from budget_bill_schedule import due_in_month
        from budget_bills_service import candidates
        imported={r['id']:r['date'][:7] for r in db.execute('''SELECT e.id,e.date FROM budget_import_rows r
            JOIN budget_entries_v2 e ON e.id=r.entry_id WHERE r.session_id=? AND e.kind='EXPENSE' ''',(session_id,))}
        matches=[]
        for month in sorted(set(imported.values())):
            for bill in db.execute('SELECT * FROM budget_bills_v2 WHERE active=1 AND account_id=?',(session['account_id'],)):
                if not due_in_month(bill,month) or db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE bill_id=? AND month=?',(bill['id'],month)).fetchone():continue
                found=[e for e in candidates(db,bill,month) if e['id'] in imported]
                if found: matches.append(dict(bill_id=bill['id'],title=bill['title'],month=month,entry_ids=[e['id'] for e in found]))
        result['bill_matches']=matches
        db.execute('''UPDATE budget_import_sessions SET status='COMMITTED',version=version+1,commit_request_id=?,commit_payload=?,result_json=? WHERE id=?''',
                   (token, fingerprint, json.dumps(result), session_id))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction:
            db.rollback()

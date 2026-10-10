"""Local receipt drafts; attaching or classifying an existing purchase is cash-neutral."""
import hashlib
import json
from uuid import uuid4

from api.exceptions import ApiError, NotFoundError, ValidationError
from database import get_db
from budget_bank_import_service import entries_matching
from budget_category_service import category, require_version, rule_match, rules, set_lines
from budget_import_parser import parse_receipt, parsed_date
from budget_reserves_service import _account, _fingerprint, _now, _request_id
from routes_budget_workspace import MAX_RECEIPT_BYTES, RECEIPT_TYPES, cents, insert_entry, positive_id, receipt_dir, text_field
import receipt_ocr_service


def draft_row(db, draft_id, include_deleted=False):
    row = db.execute('SELECT * FROM budget_receipt_drafts WHERE id=?', (draft_id,)).fetchone()
    if not row or (row['status'] == 'DELETED' and not include_deleted):
        raise NotFoundError('Paragon nie istnieje.')
    return row


def delete(draft_id, version):
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        row = draft_row(db, draft_id, include_deleted=True)
        if row['status'] != 'DELETED':
            require_version(row, version, 'Paragony')
            # Remove only this attachment, including when a newer one replaced it.
            db.execute('''UPDATE budget_entries_v2 SET receipt_filename=NULL,
                receipt_original_name=NULL,version=version+1 WHERE id=? AND receipt_filename=?''',
                (row['entry_id'], row['filename']))
            db.execute('''UPDATE budget_receipt_drafts SET status='DELETED',entry_id=NULL,
                raw_text='',data_json='{}',warnings_json='[]',version=version+1 WHERE id=?''', (draft_id,))
        referenced = db.execute('SELECT 1 FROM budget_entries_v2 WHERE receipt_filename=?', (row['filename'],)).fetchone() \
            or db.execute("SELECT 1 FROM budget_receipt_drafts WHERE filename=? AND status!='DELETED'", (row['filename'],)).fetchone()
        db.commit()
        if not referenced:
            (receipt_dir()/row['filename']).unlink(missing_ok=True)
        return dict(deleted=draft_id)
    except Exception:
        db.rollback()
        raise


def upload(upload, data):
    if not upload or upload.mimetype not in RECEIPT_TYPES:
        raise ValidationError('Wybierz zdjęcie JPG, PNG, WebP lub PDF.')
    content = upload.read(MAX_RECEIPT_BYTES+1)
    if not content or len(content) > MAX_RECEIPT_BYTES:
        raise ValidationError('Paragon musi być niepustym plikiem do 8 MB.')
    extension, signature = RECEIPT_TYPES[upload.mimetype]
    if not content.startswith(signature) or (upload.mimetype == 'image/webp' and content[8:12] != b'WEBP'):
        raise ValidationError('Zawartość nie zgadza się z formatem pliku.')
    account_id = positive_id(data['account_id'], 'konto') if data.get('account_id') is not None else None
    token, file_hash = _request_id(data), hashlib.sha256(content).hexdigest()
    fingerprint = _fingerprint(dict(account_id=account_id, file_hash=file_hash))
    db = get_db()
    previous = db.execute('SELECT * FROM budget_receipt_drafts WHERE request_id=?', (token,)).fetchone()
    if previous:
        if previous['request_payload'] != fingerprint:
            raise ApiError('receipt_request_conflict', 'Ten paragon przyjęto z innymi danymi.', status=409)
        if previous['status'] == 'DELETED':
            raise ApiError('receipt_deleted', 'Ten paragon został usunięty. Wybierz plik ponownie.', status=409)
        return dict(id=previous['id'])
    same = db.execute("SELECT id FROM budget_receipt_drafts WHERE file_hash=? AND status IN ('PENDING','COMMITTED') ORDER BY id DESC LIMIT 1", (file_hash,)).fetchone()
    if same:
        return dict(id=same['id'])
    if account_id:
        _account(db, account_id)
    folder = receipt_dir(); folder.mkdir(parents=True, exist_ok=True)
    filename = uuid4().hex+extension
    path = folder/filename
    path.write_bytes(content)
    try:
        text, warnings = receipt_ocr_service.extract(path)
        parsed, parse_warnings = parse_receipt(text)
        matched, rule_warnings = rule_match(rules(db), account_id, parsed['merchant'], parsed['merchant'])
        parsed['category_id'] = matched['category_id'] if matched else None
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT * FROM budget_receipt_drafts WHERE request_id=?', (token,)).fetchone()
        if previous:
            if previous['request_payload'] != fingerprint:
                raise ApiError('receipt_request_conflict', 'Ten paragon przyjęto z innymi danymi.', status=409)
            if previous['status'] == 'DELETED':
                raise ApiError('receipt_deleted', 'Ten paragon został usunięty. Wybierz plik ponownie.', status=409)
            path.unlink(missing_ok=True)
            return dict(id=previous['id'])
        draft_id = db.execute('''INSERT INTO budget_receipt_drafts
            (account_id,filename,original_name,file_hash,raw_text,data_json,warnings_json,request_id,request_payload,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''', (account_id, filename, text_field(upload.filename or 'paragon'+extension, 'Nazwa pliku', 150),
            file_hash, text, json.dumps(parsed, ensure_ascii=False), json.dumps(warnings+parse_warnings+rule_warnings, ensure_ascii=False), token, fingerprint, _now())).lastrowid
        db.commit()
        return dict(id=draft_id)
    except Exception:
        db.rollback(); path.unlink(missing_ok=True)
        raise
    finally:
        if db.in_transaction:
            db.rollback()


def view(draft_id):
    db = get_db(); row = draft_row(db, draft_id); parsed = json.loads(row['data_json'])
    matches = entries_matching(db, row['account_id'], parsed['date'], round(parsed['amount']*100) if parsed['amount'] else 0,
                              merchant=parsed['merchant'], window=3)
    return dict(id=row['id'], version=row['version'], status=row['status'], account_id=row['account_id'], entry_id=row['entry_id'],
                filename=row['original_name'], is_pdf=row['filename'].endswith('.pdf'), raw_text=row['raw_text'],
                data=parsed, warnings=json.loads(row['warnings_json']), candidates=matches)


def reparse(draft_id, data):
    return save_readout(draft_id, data.get('version'), data.get('text'), [])


def recognize(draft_id, data):
    db = get_db(); row = draft_row(db, draft_id)
    require_version(row, data.get('version'), 'Paragony')
    if row['status'] != 'PENDING':
        raise ValidationError('Ponowny odczyt jest dostępny dla paragonów do sprawdzenia.')
    path = receipt_dir()/row['filename']
    if not path.is_file():
        raise NotFoundError('Plik paragonu nie istnieje.')
    # Recognition runs outside the write transaction. Guard the version again
    # afterwards so it cannot overwrite a concurrent edit, deletion or commit.
    text, warnings = receipt_ocr_service.extract(path)
    if not text.strip():
        raise ValidationError('Nie udało się ponownie odczytać zdjęcia. Zachowano poprzednie dane; możesz uzupełnić je ręcznie.')
    return save_readout(draft_id, data.get('version'), text, warnings)


def save_readout(draft_id, version, text, ocr_warnings):
    parsed, warnings = parse_receipt(text)
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE'); row = draft_row(db, draft_id)
        require_version(row, version, 'Paragony')
        if row['status'] != 'PENDING':
            raise ValidationError('Ten paragon jest już zapisany.')
        matched, rule_warnings = rule_match(rules(db), row['account_id'], parsed['merchant'], parsed['merchant'])
        parsed['category_id'] = matched['category_id'] if matched else None
        db.execute('UPDATE budget_receipt_drafts SET raw_text=?,data_json=?,warnings_json=?,version=version+1 WHERE id=?',
                   (text, json.dumps(parsed, ensure_ascii=False), json.dumps(ocr_warnings+warnings+rule_warnings, ensure_ascii=False), draft_id))
        db.commit()
        return dict(id=draft_id)
    except Exception:
        db.rollback()
        raise


def commit(draft_id, data):
    token, fingerprint, db = _request_id(data), _fingerprint(dict(data, draft_id=draft_id)), get_db()
    action = data.get('action')
    if action not in ('MATCH', 'NEW'):
        raise ValidationError('Wybierz istniejący zakup lub nowy wydatek.')
    mode = data.get('classification_mode', 'KEEP')
    if mode not in ('KEEP', 'GENERAL', 'SPLIT'):
        raise ValidationError('Wybierz sposób przypisania kategorii.')
    old_filename = None
    try:
        db.execute('BEGIN IMMEDIATE'); draft = draft_row(db, draft_id)
        if draft['commit_request_id']:
            if draft['commit_request_id'] == token and draft['commit_payload'] == fingerprint:
                return dict(entry_id=draft['entry_id'], linked=action=='MATCH')
            raise ApiError('receipt_closed', 'Ten paragon został już zapisany. Odśwież dane.', status=409)
        require_version(draft, data.get('version'), 'Paragony')
        if draft['status'] != 'PENDING' or not (receipt_dir()/draft['filename']).is_file():
            raise ValidationError('Paragon nie jest gotowy do zapisu.')
        account_id, amount = positive_id(data.get('account_id'), 'konto'), cents(data.get('amount'))
        account = _account(db, account_id)
        day = parsed_date(data.get('date'))
        merchant = text_field(data.get('merchant') or 'Zakup z paragonu', 'Sklep', 150)
        duplicate = db.execute("SELECT entry_id FROM budget_receipt_drafts WHERE file_hash=? AND status='COMMITTED' AND entry_id IS NOT NULL AND id!=?", (draft['file_hash'], draft_id)).fetchone()
        if duplicate and (action != 'MATCH' or duplicate['entry_id'] != data.get('entry_id')):
            raise ApiError('receipt_duplicate', 'To zdjęcie jest już powiązane z innym wydatkiem.', status=409)
        if action == 'MATCH':
            entry_id = positive_id(data.get('entry_id'), 'zakup')
            entry = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (entry_id,)).fetchone()
            if not entry or entry['kind'] != 'EXPENSE' or (entry['account_id'], entry['amount_cents']) != (account_id, amount):
                raise ValidationError('Kwota i konto paragonu muszą odpowiadać wybranemu zakupowi.')
            require_version(entry, data.get('entry_version'), 'Zakupy')
            old_filename = entry['receipt_filename']
        else:
            effect = data.get('balance_mode', 'HISTORY')
            if effect not in ('HISTORY', 'APPLY'):
                raise ValidationError('Wybierz wpływ nowego wydatku na saldo.')
            if effect == 'APPLY' and data.get('expected_balance') != float(account['balance']):
                raise ApiError('receipt_balance_conflict', 'Saldo konta zmieniło się. Odśwież dane przed zapisaniem nowego wydatku.', status=409)
            # A likely existing purchase requires an explicit override, even if
            # the user selected NEW. This catches accidental double bookkeeping.
            candidates = entries_matching(db, account_id, day, amount, merchant=merchant, window=3)
            if candidates and data.get('confirm_separate') is not True:
                raise ValidationError('Znaleziono podobny zakup. Połącz go lub potwierdź, że to odrębny wydatek.')
            entry_id = insert_entry(db, dict(account_id=account_id, kind='EXPENSE', amount_cents=amount, date=day,
                description=merchant, merchant=merchant,
                cash_effect=int(effect=='APPLY'), lines=[]))
            entry = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (entry_id,)).fetchone()
        if mode == 'SPLIT':
            if not isinstance(data.get('lines'), list) or not data['lines']:
                raise ValidationError('Podział wymaga pozycji z kwotami i kategoriami.')
            set_lines(db, entry, lines=data.get('lines'))
        elif mode == 'GENERAL':
            category(db, data.get('category_id'))
            set_lines(db, entry, category_id=data.get('category_id'))
        elif action == 'NEW':
            set_lines(db, entry)
        db.execute('UPDATE budget_entries_v2 SET receipt_filename=?,receipt_original_name=?,version=version+1 WHERE id=?',
                   (draft['filename'], draft['original_name'], entry_id))
        # Save corrected purchase metadata alongside the original OCR text.
        corrected = dict(merchant=str(data.get('merchant') or '')[:150], date=day, amount=amount/100,
                         category_id=data.get('category_id'), lines=data.get('lines', []))
        db.execute('''UPDATE budget_receipt_drafts SET status='COMMITTED',entry_id=?,account_id=?,data_json=?,
            commit_request_id=?,commit_payload=?,version=version+1 WHERE id=?''',
            (entry_id, account_id, json.dumps(corrected, ensure_ascii=False), token, fingerprint, draft_id))
        db.commit()
        if old_filename and old_filename != draft['filename'] and not db.execute('SELECT 1 FROM budget_receipt_drafts WHERE filename=?', (old_filename,)).fetchone():
            (receipt_dir()/old_filename).unlink(missing_ok=True)
        return dict(entry_id=entry_id, linked=action=='MATCH')
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction:
            db.rollback()

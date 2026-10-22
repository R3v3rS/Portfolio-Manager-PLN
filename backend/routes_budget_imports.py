"""Budget imports have their own review area, separate from investment imports."""
import json
from flask import Blueprint, request, send_from_directory
from api.exceptions import ValidationError
from api.response import success_response
from budget_category_hierarchy_service import category_options
from database import get_db
from routes_budget_workspace import body, cents, positive_id, receipt_dir
from budget_import_parser import MAX_FILE_BYTES, parsed_date
import budget_bank_import_service as bank
import budget_category_service as categories
import budget_receipts_service as receipts
import receipt_ocr_service
import budget_reserve_funding_service as funding

imports_bp = Blueprint('budget_imports', __name__)


def file_content():
    upload = request.files.get('file')
    if not upload:
        raise ValidationError('Wybierz plik CSV.')
    return upload, upload.read(MAX_FILE_BYTES+1)


def form_json():
    try:
        value = json.loads(request.form.get('data', '{}'))
    except (ValueError, TypeError):
        raise ValidationError('Nieprawidłowe ustawienia pliku.') from None
    if not isinstance(value, dict):
        raise ValidationError('Nieprawidłowe ustawienia pliku.')
    return value


@imports_bp.get('/', strict_slashes=False)
def workspace():
    db = get_db()
    try:
        limit = int(request.args.get('limit', 200))
        if not 1 <= limit <= 5000:
            raise ValueError
    except ValueError:
        raise ValidationError('Nieprawidłowa liczba wydatków.') from None
    pending = []
    for row in db.execute('''SELECT e.*,a.name account_name FROM budget_entries_v2 e JOIN budget_accounts a ON a.id=e.account_id
        WHERE e.kind='EXPENSE' AND e.classification_status='UNASSIGNED' ORDER BY e.date DESC,e.id DESC LIMIT ?''', (limit,)):
        pending.append(dict(id=row['id'], account_id=row['account_id'], account_name=row['account_name'], amount=row['amount_cents']/100,
            date=row['date'], description=row['description'], merchant=row['merchant'], version=row['version'], has_receipt=bool(row['receipt_filename'])))
    selected = None
    if request.args.get('entry_id'):
        entry_id = positive_id(request.args['entry_id'], 'wydatek')
        row = db.execute("SELECT e.*,a.name account_name FROM budget_entries_v2 e JOIN budget_accounts a ON a.id=e.account_id WHERE e.id=? AND e.kind='EXPENSE'", (entry_id,)).fetchone()
        if row:
            selected = bank.entry_view(db, row)
    return success_response(dict(
        accounts=[dict(r) for r in db.execute('''SELECT a.id,a.name,a.balance,a.account_type,(SELECT MAX(date) FROM budget_account_reconciliations r WHERE r.account_id=a.id AND r.record_type='RECONCILIATION') verified_on
            FROM budget_accounts a WHERE UPPER(COALESCE(a.currency,'PLN'))='PLN' ORDER BY a.id''')],
        categories=category_options(db, include_unassigned=False),
        rules=categories.rules(db), transfer_rules=funding.rules(db),
        reserves=[dict(r) for r in db.execute('SELECT id,name,version FROM budget_reserves WHERE is_archived=0 AND completed_at IS NULL ORDER BY name')], pending=pending,
        pending_count=db.execute("SELECT COUNT(*) FROM budget_entries_v2 WHERE kind='EXPENSE' AND classification_status='UNASSIGNED'").fetchone()[0],
        sessions=[dict(r) for r in db.execute('''SELECT s.id,s.filename,s.created_at,s.status,s.version,s.balance_mode,a.name account_name,
            (SELECT COUNT(*) FROM budget_import_rows r WHERE r.session_id=s.id) row_count FROM budget_import_sessions s
            JOIN budget_accounts a ON a.id=s.account_id ORDER BY s.id DESC LIMIT 30''')],
        receipts=[dict(r) for r in db.execute("SELECT id,original_name filename,status,entry_id,created_at FROM budget_receipt_drafts WHERE status!='DELETED' ORDER BY id DESC LIMIT 30")],
        ocr=dict(local=True, available=receipt_ocr_service.available()), selected_entry=selected,
    ))


@imports_bp.post('/csv/preview')
def preview_csv():
    _, content = file_content()
    return success_response(bank.preview(content, form_json().get('header_index')))


@imports_bp.post('/csv')
def stage_csv():
    upload, content = file_content()
    return success_response(bank.stage(content, upload.filename, form_json()), status=201)


@imports_bp.get('/sessions/<int:session_id>')
def session(session_id):
    return success_response(bank.view(session_id))


@imports_bp.put('/sessions/<int:session_id>/rows/<int:row_id>')
def edit_row(session_id, row_id):
    return success_response(bank.update_row(session_id, row_id, body()))


@imports_bp.post('/sessions/<int:session_id>/refresh')
def refresh_session(session_id):
    return success_response(bank.refresh(session_id, body()))


@imports_bp.post('/sessions/<int:session_id>/commit')
def commit_session(session_id):
    return success_response(bank.commit(session_id, body()))


@imports_bp.post('/rules')
def create_rule():
    return success_response(categories.save_rule(body()), status=201)


@imports_bp.put('/rules/<int:rule_id>')
def edit_rule(rule_id):
    return success_response(categories.save_rule(body(), rule_id))


@imports_bp.post('/categorize')
def categorize():
    return success_response(categories.categorize(body()))


@imports_bp.post('/transfer-rules')
def create_transfer_rule():
    return success_response(funding.save_rule(body()), status=201)


@imports_bp.put('/transfer-rules/<int:rule_id>')
def edit_transfer_rule(rule_id):
    return success_response(funding.save_rule(body(),rule_id))


@imports_bp.get('/matches')
def matches():
    amount = cents(request.args.get('amount'))
    day = parsed_date(request.args.get('date'))
    account_id = positive_id(request.args['account_id'], 'konto') if request.args.get('account_id') else None
    return success_response(bank.entries_matching(get_db(), account_id, day, amount, merchant=request.args.get('merchant', '')[:150], window=3))


@imports_bp.post('/categorize/rules')
def apply_rules():
    return success_response(categories.apply_rules(body()))


@imports_bp.post('/receipts')
def upload_receipt():
    return success_response(receipts.upload(request.files.get('file'), form_json()), status=201)


@imports_bp.get('/receipts/<int:draft_id>')
def receipt(draft_id):
    return success_response(receipts.view(draft_id))


@imports_bp.delete('/receipts/<int:draft_id>')
def delete_receipt(draft_id):
    return success_response(receipts.delete(draft_id, request.args.get('version', type=int)))


@imports_bp.get('/receipts/<int:draft_id>/file')
def receipt_file(draft_id):
    row = receipts.draft_row(get_db(), draft_id)
    response = send_from_directory(receipt_dir(), row['filename'])
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@imports_bp.post('/receipts/<int:draft_id>/parse')
def reparse(draft_id):
    return success_response(receipts.reparse(draft_id, body()))


@imports_bp.post('/receipts/<int:draft_id>/recognize')
def recognize_receipt(draft_id):
    return success_response(receipts.recognize(draft_id, body()))


@imports_bp.post('/receipts/<int:draft_id>/commit')
def commit_receipt(draft_id):
    return success_response(receipts.commit(draft_id, body()))

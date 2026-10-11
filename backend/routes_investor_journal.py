from flask import Blueprint, request
from api.exceptions import ValidationError
from api.response import success_response
import investor_journal_service as journal

journal_bp = Blueprint('investor_journal', __name__)


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValidationError('Nieprawidłowe dane dziennika.')
    return value


@journal_bp.get('/', strict_slashes=False)
def list_entries():
    return success_response(journal.workspace(request.args))


@journal_bp.get('/export')
def export_entries():
    return success_response(journal.export())


@journal_bp.get('/<int:entry_id>')
def get_entry(entry_id):
    return success_response(journal.detail(entry_id))


@journal_bp.post('/', strict_slashes=False)
def create_entry():
    return success_response(journal.save(body()), status=201)


@journal_bp.put('/<int:entry_id>')
def update_entry(entry_id):
    return success_response(journal.save(body(), entry_id))


@journal_bp.put('/<int:entry_id>/archive')
def archive_entry(entry_id):
    return success_response(journal.archive(entry_id, body()))


@journal_bp.post('/<int:entry_id>/reviews')
def create_review(entry_id):
    return success_response(journal.add_review(entry_id, body()), status=201)

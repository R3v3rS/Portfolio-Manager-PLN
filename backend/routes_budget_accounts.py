from flask import Blueprint
from api.response import success_response
from routes_budget_workspace import body
import budget_accounts_service as accounts

accounts_bp = Blueprint('budget_accounts_workspace', __name__)


@accounts_bp.get('/')
def list_accounts():
    return success_response(accounts.workspace())


@accounts_bp.post('/transfers')
def transfer_accounts():
    return success_response(accounts.transfer(body()),status=201)


@accounts_bp.post('/')
def create_account():
    return success_response(accounts.create(body()),status=201)


@accounts_bp.post('/<int:account_id>/reconcile')
def reconcile_account(account_id):
    return success_response(accounts.reconcile(account_id,body()),status=201)


@accounts_bp.post('/<int:account_id>/opening-balance')
def set_opening_balance(account_id):
    return success_response(accounts.set_opening_balance(account_id,body()),status=201)

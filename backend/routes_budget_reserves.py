from flask import Blueprint, request
from api.response import success_response
from routes_budget_workspace import body
import budget_reserves_service as reserves

reserves_bp = Blueprint('budget_reserves', __name__)


@reserves_bp.get('/', strict_slashes=False)
def list_reserves():
    result = reserves.workspace()
    from budget_reserve_history_service import enrich_workspace
    return success_response(enrich_workspace(result,request.args.get('month')))


@reserves_bp.post('/<int:reserve_id>/preview')
def movement_preview(reserve_id):
    from budget_reserve_operations_service import preview
    return success_response(preview(reserve_id,body()))


@reserves_bp.get('/funding-plan')
def funding_plan():
    from budget_reserve_operations_service import funding_plan
    return success_response(funding_plan())


@reserves_bp.post('/funding-preview')
def funding_preview():
    from budget_reserve_operations_service import fund_batch
    return success_response(fund_batch(body(),dry_run=True))


@reserves_bp.post('/funding')
def funding_batch():
    from budget_reserve_operations_service import fund_batch
    return success_response(fund_batch(body()),status=201)


@reserves_bp.post('/', strict_slashes=False)
def create_reserve():
    return success_response(reserves.save(body()), status=201)


@reserves_bp.put('/<int:reserve_id>')
def update_reserve(reserve_id):
    return success_response(reserves.save(body(),reserve_id))


@reserves_bp.post('/<int:reserve_id>/movements')
def add_movement(reserve_id):
    return success_response(reserves.move(reserve_id,body()), status=201)


@reserves_bp.put('/<int:reserve_id>/archive')
def archive_reserve(reserve_id):
    return success_response(reserves.archive(reserve_id,body()))

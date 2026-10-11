from flask import Blueprint
from api.response import success_response
from routes_budget_workspace import body
import budget_reserves_service as reserves

reserves_bp = Blueprint('budget_reserves', __name__)


@reserves_bp.get('/', strict_slashes=False)
def list_reserves():
    return success_response(reserves.workspace())


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

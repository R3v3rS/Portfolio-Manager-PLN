from flask import Blueprint
from api.response import success_response
from routes_budget_workspace import body
import budget_planning_service as planning

planning_bp=Blueprint('budget_planning',__name__)


@planning_bp.put('/settings')
def update_settings(): return success_response(planning.save_settings(body()))


@planning_bp.put('/reserve-plans/<int:reserve_id>')
def update_reserve_plan(reserve_id): return success_response(planning.save_reserve_plan(reserve_id,body()))


@planning_bp.put('/category-policies/<int:category_id>')
def update_policy(category_id): return success_response(planning.save_policy(category_id,body()))


@planning_bp.post('/close-month')
def close_month(): return success_response(planning.close_month(body()),status=201)


@planning_bp.post('/purchases')
def create_purchase(): return success_response(planning.save_purchase(body()),status=201)


@planning_bp.put('/purchases/<int:purchase_id>')
def update_purchase(purchase_id): return success_response(planning.save_purchase(body(),purchase_id))

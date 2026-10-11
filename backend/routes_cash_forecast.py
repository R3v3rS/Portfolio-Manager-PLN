from flask import Blueprint, request
from api.response import success_response
from routes_budget_workspace import body
import cash_forecast_service as forecast
import expected_income_service as incomes

forecast_bp=Blueprint('cash_forecast',__name__)


@forecast_bp.get('/',strict_slashes=False)
def cash_forecast():return success_response(forecast.workspace(dict(request.args)))


@forecast_bp.post('/incomes')
def create_income():return success_response(incomes.save(body()),status=201)


@forecast_bp.put('/incomes/<int:income_id>')
def update_income(income_id):return success_response(incomes.save(body(),income_id))


@forecast_bp.put('/incomes/<int:income_id>/active')
def activate_income(income_id):return success_response(incomes.set_active(income_id,body()))


@forecast_bp.post('/incomes/<int:income_id>/receive')
def receive_income(income_id):return success_response(incomes.receive(income_id,body()),status=201)

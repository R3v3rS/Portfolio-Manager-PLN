from flask import request

from bond_service import BondService
from portfolio_service import PortfolioService
from api.response import success_response
from api.exceptions import NotFoundError, ValidationError
from routes_portfolio_base import (
    portfolio_bp,
    optional_number,
    optional_string,
    raise_portfolio_validation_error,
    require_json_body,
    require_non_empty_string,
    require_number,
    require_positive_int,
)


@portfolio_bp.route('/limits', methods=['GET'])
def get_tax_limits():
    limits = PortfolioService.get_tax_limits()
    return success_response({'limits': limits})


@portfolio_bp.route('/create', methods=['POST'])
def create_portfolio():
    data = require_json_body()
    name = require_non_empty_string(data, 'name')
    initial_cash = optional_number(data, 'initial_cash', default=0.0, non_negative=True)
    account_type = optional_string(data, 'account_type') or 'STANDARD'
    created_at = optional_string(data, 'created_at')

    portfolio_id = PortfolioService.create_portfolio(
        name,
        initial_cash,
        account_type,
        created_at,
    )
    return success_response({'id': portfolio_id, 'message': 'Portfolio created successfully'}, status=201)


@portfolio_bp.route('/list', methods=['GET'])
def list_portfolios():
    portfolios = PortfolioService.list_portfolios()
    result = []
    for portfolio in portfolios:
        value_data = PortfolioService.get_portfolio_value(portfolio['id'])
        portfolio.update(value_data)
        result.append(portfolio)
    return success_response({'portfolios': result})


@portfolio_bp.route('/value/<int:portfolio_id>', methods=['GET'])
def get_value(portfolio_id):
    value_data = PortfolioService.get_portfolio_value(portfolio_id)
    if not value_data:
        raise NotFoundError('Portfolio not found')
    return success_response(value_data)


@portfolio_bp.route('/holdings/<int:portfolio_id>', methods=['GET'])
def get_holdings(portfolio_id):
    force_refresh = False
    refresh_value = request.args.get('refresh')
    if refresh_value is not None:
        if refresh_value not in {'0', '1'}:
            raise ValidationError('Field refresh must be 0 or 1', details={'field': 'refresh'})
        force_refresh = refresh_value == '1'
    holdings = PortfolioService.get_holdings(portfolio_id, force_price_refresh=force_refresh)
    return success_response({'holdings': holdings})


@portfolio_bp.route('/<int:portfolio_id>/clear', methods=['POST'])
def clear_portfolio(portfolio_id):
    try:
        result = PortfolioService.clear_portfolio_data(portfolio_id)
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Portfolio data cleared successfully', **result})


@portfolio_bp.route('/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    try:
        PortfolioService.delete_portfolio(portfolio_id)
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Portfolio deleted successfully'})


@portfolio_bp.route('/bonds/<int:portfolio_id>', methods=['GET'])
def get_bonds(portfolio_id):
    bonds = BondService.get_bonds(portfolio_id)
    return success_response({'bonds': bonds})


@portfolio_bp.route('/bonds', methods=['POST'])
def add_bond():
    data = require_json_body()
    try:
        BondService.add_bond(
            require_positive_int(data, 'portfolio_id'),
            require_non_empty_string(data, 'name'),
            require_number(data, 'principal', positive=True),
            require_number(data, 'interest_rate', non_negative=True),
            require_non_empty_string(data, 'purchase_date'),
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Bond added successfully'}, status=201)


@portfolio_bp.route('/savings/rate', methods=['POST'])
def update_savings_rate():
    data = require_json_body()
    try:
        PortfolioService.update_savings_rate(
            require_positive_int(data, 'portfolio_id'),
            require_number(data, 'rate', non_negative=True),
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Rate updated successfully'})


@portfolio_bp.route('/savings/interest/manual', methods=['POST'])
def add_manual_interest():
    data = require_json_body()
    try:
        PortfolioService.add_manual_interest(
            require_positive_int(data, 'portfolio_id'),
            require_number(data, 'amount', positive=True),
            require_non_empty_string(data, 'date'),
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Interest added successfully'})

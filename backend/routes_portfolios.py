from flask import request

from bond_service import BondService
from portfolio_service import PortfolioService
from api.response import success_response
from api.exceptions import NotFoundError, ValidationError, ApiError
from constants import SUBPORTFOLIOS_ALLOWED_TYPES
from job_registry import job_registry
import threading
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


@portfolio_bp.route('/config', methods=['GET'])
def get_config():
    return success_response({
        'subportfolios_allowed_types': SUBPORTFOLIOS_ALLOWED_TYPES
    })


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
    # If the request comes from the details page, we might want a flat list
    # to easily find sub-portfolios by ID without traversing the tree.
    include_children = request.args.get('tree', default='1') == '1'
    portfolios = PortfolioService.list_portfolios(include_children=include_children)
    result = []
    
    def enrich_portfolio(p, depth=0):
        value_data = PortfolioService.get_portfolio_value(p['id'], cached_prices_only=True)
        p.update(value_data)
        if depth == 0 and 'children' in p and p['children']:
            for child in p['children']:
                enrich_portfolio(child, depth=depth + 1)
        return p

    for portfolio in portfolios:
        result.append(enrich_portfolio(portfolio))
        
    return success_response({'portfolios': result})


@portfolio_bp.route('/value/<int:portfolio_id>', methods=['GET'])
def get_value(portfolio_id):
    force_refresh = request.args.get('refresh') == '1'
    value_data = PortfolioService.get_portfolio_value(
        portfolio_id,
        cached_prices_only=not force_refresh,
    )
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
    holdings = PortfolioService.get_holdings(
        portfolio_id,
        force_price_refresh=force_refresh,
        cached_prices_only=not force_refresh,
    )
    return success_response({'holdings': holdings})


@portfolio_bp.route('/allocation/<int:portfolio_id>', methods=['GET'])
def get_equity_allocation(portfolio_id):
    allocation = PortfolioService.get_equity_allocation(portfolio_id)
    return success_response({'allocation': allocation})


@portfolio_bp.route('/<int:portfolio_id>/clear', methods=['POST'])
def clear_portfolio(portfolio_id):
    try:
        result = PortfolioService.clear_portfolio_data(portfolio_id)
    except ValueError as error:
        message = str(error)
        if message in {
            'Czyszczenie sub-portfela nie jest dozwolone. Przenieś transakcje ręcznie.',
            'Najpierw zarchiwizuj sub-portfele.',
        }:
            raise ApiError('INVALID_ACTION', message, status=422) from error
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
    return success_response(BondService.create(data), status=201)


@portfolio_bp.route('/bonds/workspace/<int:portfolio_id>', methods=['GET'])
def bonds_workspace(portfolio_id):
    from bond_service import number
    assumption=request.args.get('assumed_rate')
    if assumption is not None:assumption=number(assumption,'Stopa symulacji',0,100)
    return success_response(BondService.workspace(portfolio_id,assumption))


@portfolio_bp.route('/bonds/position/<int:bond_id>', methods=['PUT'])
def update_bond(bond_id):
    return success_response(BondService.update(bond_id,require_json_body()))


@portfolio_bp.route('/bonds/position/<int:bond_id>/estimate', methods=['GET'])
def bond_estimate(bond_id):
    from bond_service import details, load, day, number
    from database import get_db
    as_of=day(request.args.get('date'),'Data symulacji',True)
    rate=request.args.get('assumed_rate')
    if rate is not None:rate=number(rate,'Stopa symulacji',0,100)
    db=get_db();bond=load(db,bond_id)
    if as_of.isoformat()<bond['purchase_date']:raise ValidationError('Symulacja nie może poprzedzać zakupu.')
    return success_response(details(db,bond,as_of,rate))


@portfolio_bp.route('/bonds/position/<int:bond_id>/<action>', methods=['POST'])
def bond_action(bond_id,action):
    method={'rate':BondService.rate,'settle':BondService.settle,'cancel':BondService.cancel}.get(action)
    if not method:raise NotFoundError('Nie znaleziono działania obligacji.')
    return success_response(method(bond_id,require_json_body()))


@portfolio_bp.route('/bonds/import/preview', methods=['POST'])
def bond_import_preview():
    data=require_json_body()
    return success_response(BondService.preview_import(require_positive_int(data,'portfolio_id'),data.get('text')))


@portfolio_bp.route('/bonds/import/book', methods=['POST'])
def bond_import_book():
    return success_response(BondService.import_rows(require_json_body()),status=201)


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


@portfolio_bp.route('/<int:parent_id>/children', methods=['POST'])
def create_child_portfolio(parent_id):
    data = require_json_body()
    name = require_non_empty_string(data, 'name')
    initial_cash = optional_number(data, 'initial_cash', default=0.0, non_negative=True)
    created_at = optional_string(data, 'created_at')

    parent = PortfolioService.get_portfolio(parent_id)
    if not parent:
        raise NotFoundError('Parent portfolio not found')
    
    if parent['account_type'] not in SUBPORTFOLIOS_ALLOWED_TYPES:
        raise ApiError('INVALID_ACCOUNT_TYPE', f'Sub-portfolios are only allowed for types: {SUBPORTFOLIOS_ALLOWED_TYPES}', status=422)
    
    if parent.get('parent_portfolio_id'):
        raise ApiError('DEEP_NESTING_ERROR', 'Maximum one level of nesting is allowed', status=422)

    # Create child portfolio (it inherits parent's account_type)
    child_id = PortfolioService.create_portfolio(
        name,
        initial_cash,
        parent['account_type'],
        created_at,
        parent_portfolio_id=parent_id
    )
    return success_response({'id': child_id, 'message': 'Child portfolio created successfully'}, status=201)


@portfolio_bp.route('/<int:portfolio_id>/archive', methods=['POST'])
def archive_portfolio(portfolio_id):
    portfolio = PortfolioService.get_portfolio(portfolio_id)
    if not portfolio:
        raise NotFoundError('Portfolio not found')
    
    if not portfolio.get('parent_portfolio_id'):
        raise ApiError('INVALID_ACTION', 'Only child portfolios can be archived', status=422)

    PortfolioService.archive_portfolio(portfolio_id)
    return success_response({'message': 'Portfolio archived successfully'})


@portfolio_bp.route('/jobs/<string:job_id>', methods=['GET'])
def get_job_status(job_id):
    job = job_registry.get_job(job_id)
    if not job:
        raise NotFoundError('Job not found')
    
    # Simple serialization of datetime objects
    response_job = {**job}
    response_job['created_at'] = job['created_at'].isoformat()
    response_job['updated_at'] = job['updated_at'].isoformat()
    
    return success_response(response_job)


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


@portfolio_bp.route('/audit/consistency', methods=['GET'])
def get_consistency_audit():
    result = PortfolioService.get_parent_child_consistency_audit()
    return success_response(result)


@portfolio_bp.route('/transfer/asset', methods=['POST'])
def transfer_asset():
    from asset_transfer_service import transfer
    return success_response(transfer(require_json_body()), status=201)


@portfolio_bp.route('/transfer/assets/<int:portfolio_id>', methods=['GET'])
def asset_transfer_positions(portfolio_id):
    from database import get_db
    db=get_db()
    parent=db.execute('SELECT * FROM portfolios WHERE id=?',(portfolio_id,)).fetchone()
    if not parent or parent['parent_portfolio_id'] or parent['is_archived']:
        raise ValidationError('Wybierz główny portfel.')
    scopes=[{'id':None,'name':'Część główna'}]+[dict(r) for r in db.execute('SELECT id,name FROM portfolios WHERE parent_portfolio_id=? AND is_archived=0',(portfolio_id,))]
    positions=[]
    for scope in scopes:
        for h in PortfolioService.get_holdings(portfolio_id,sub_portfolio_id=scope['id'],aggregate=False,cached_prices_only=True):
            positions.append(dict(h,source_id=scope['id'],source_name=scope['name']))
    return success_response({'positions':positions,'scopes':scopes})


@portfolio_bp.route('/manual-price/<string:ticker>', methods=['PUT', 'DELETE'])
def manual_stock_price(ticker):
    from manual_stock_prices import save
    payload = require_json_body()
    return success_response(save(ticker, payload, clear=request.method=='DELETE' or payload.get('clear') is True))

from flask import Blueprint, request

from api.response import success_response
from instrument_profile_service import (
    AiClassificationService,
    CategoryService,
    EtfAllocationService,
    InstrumentProfileService,
)
from routes_portfolio_base import require_json_body

instrument_profiles_bp = Blueprint('instrument_profiles', __name__)


@instrument_profiles_bp.route('/api/instrument-profiles', methods=['GET'])
def list_profiles():
    return success_response(InstrumentProfileService.list_profiles())


@instrument_profiles_bp.route('/api/instrument-profiles', methods=['POST'])
def create_profile():
    payload = require_json_body()
    return success_response(InstrumentProfileService.create_or_update_profile(payload), status=201)


@instrument_profiles_bp.route('/api/instrument-profiles/<string:ticker>', methods=['GET'])
def get_profile(ticker: str):
    return success_response(InstrumentProfileService.get_profile(ticker))


@instrument_profiles_bp.route('/api/instrument-profiles/<string:ticker>', methods=['PUT'])
def update_profile(ticker: str):
    payload = require_json_body()
    payload['ticker'] = ticker
    return success_response(InstrumentProfileService.create_or_update_profile(payload))


@instrument_profiles_bp.route('/api/instrument-profiles/<string:ticker>/ai-classify', methods=['POST'])
def ai_classify_profile(ticker: str):
    payload = require_json_body()
    return success_response(AiClassificationService.classify_instrument(ticker, payload.get('name', ''), payload.get('description', '')))


@instrument_profiles_bp.route('/api/etf-allocations/<string:ticker>', methods=['GET'])
def get_etf_allocations(ticker: str):
    return success_response(EtfAllocationService.get_allocations(ticker))


@instrument_profiles_bp.route('/api/etf-allocations/<string:ticker>', methods=['PUT'])
def replace_etf_allocations(ticker: str):
    payload = require_json_body()
    return success_response(EtfAllocationService.replace_allocations(ticker, payload.get('allocations', [])))


@instrument_profiles_bp.route('/api/instrument-profiles/<string:ticker>/ai-classify-etf', methods=['POST'])
def ai_classify_etf(ticker: str):
    payload = require_json_body()
    return success_response(AiClassificationService.classify_etf(payload.get('text', '')))


@instrument_profiles_bp.route('/api/categories', methods=['GET'])
def list_categories():
    category_type = request.args.get('type', '')
    return success_response(CategoryService.get_all(category_type))


@instrument_profiles_bp.route('/api/categories', methods=['POST'])
def create_category():
    payload = require_json_body()
    category_id = CategoryService.resolve(payload.get('name', ''), payload.get('type', ''))
    return success_response({'id': category_id}, status=201)

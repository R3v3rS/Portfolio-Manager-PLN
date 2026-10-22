from flask import Blueprint, request
from api.response import success_response
from api.exceptions import ValidationError
from routes_portfolio_base import require_json_body
import investment_ai_service as service
from investment_ai_context import build
from investment_ai_provider import settings, save_settings

ai_bp = Blueprint('ai', __name__)

@ai_bp.post('/api/ai/portfolio-analysis')
def portfolio_analysis():
    return success_response(service.ask(require_json_body()))

@ai_bp.get('/api/ai/settings')
def get_settings():
    return success_response(settings())

@ai_bp.put('/api/ai/settings')
def update_settings():
    return success_response(save_settings(require_json_body()))

@ai_bp.get('/api/ai/context/<int:pid>')
def context(pid):
    scope = request.args.get('include_subportfolios','1')
    if scope not in ('0','1'): raise ValidationError('Wybierz zakres portfela.')
    return success_response(build(pid,scope=='1',request.args.get('from'),request.args.get('to')))

@ai_bp.get('/api/ai/sessions/<int:pid>')
def sessions(pid):
    return success_response(service.sessions(pid))

@ai_bp.get('/api/ai/session/<sid>')
def session(sid):
    return success_response(service.session(sid))

@ai_bp.post('/api/ai/messages/<mid>/journal')
def journal(mid):
    return success_response(service.to_journal(mid),201)

@ai_bp.get('/api/investment-analysis/plans/<int:pid>')
def get_plan(pid):
    from investment_allocation_service import get_plan
    return success_response(get_plan(pid))

@ai_bp.put('/api/investment-analysis/plans/<int:pid>')
def save_plan(pid):
    from investment_allocation_service import save_plan
    return success_response(save_plan(pid,require_json_body()))

@ai_bp.post('/api/investment-analysis/plans/<int:pid>/simulate')
def simulate(pid):
    from investment_allocation_service import simulate
    return success_response(simulate(pid,require_json_body()))

@ai_bp.get('/api/investment-analysis/exposure/<int:pid>')
def exposure(pid):
    from investment_exposure_service import exposure
    return success_response(exposure(pid))

@ai_bp.put('/api/investment-analysis/funds/<ticker>')
def save_fund(ticker):
    from investment_exposure_service import save_composition
    return success_response(save_composition(ticker,require_json_body()))

@ai_bp.post('/api/investment-analysis/funds/<ticker>/refresh')
def refresh_fund(ticker):
    from investment_exposure_service import refresh
    return success_response(refresh(ticker))

@ai_bp.get('/api/investment-analysis/materials/<int:pid>')
def material_reviews(pid):
    from investment_material_service import reviews
    return success_response(reviews(pid))

@ai_bp.get('/api/investment-analysis/materials/<int:pid>/text')
def article_text(pid):
    from investment_article_service import saved
    return success_response(saved(pid))

@ai_bp.post('/api/investment-analysis/materials/<int:pid>/text')
def fetch_article_text(pid):
    from investment_article_service import fetch
    return success_response(fetch(pid))

@ai_bp.post('/api/investment-analysis/materials/<int:pid>/analyze')
def analyze_material(pid):
    from investment_material_service import analyze
    return success_response(analyze(pid,require_json_body()))

@ai_bp.post('/api/investment-analysis/material-reviews/<rid>/<int:index>/confirm')
def confirm_material(rid,index):
    from investment_material_service import confirm
    return success_response(confirm(rid,index,require_json_body()),201)

@ai_bp.get('/api/investment-analysis/related/<int:pid>')
def related(pid):
    from investment_material_service import related
    return success_response(related(pid))

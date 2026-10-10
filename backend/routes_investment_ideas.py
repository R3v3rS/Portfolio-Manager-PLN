from flask import Blueprint,request
from api.exceptions import ValidationError
from api.response import success_response
import investment_ideas_service as service

ideas_bp=Blueprint('investment_ideas',__name__)

def body():
    value=request.get_json(silent=True)
    if not isinstance(value,dict): raise ValidationError('Podaj poprawne dane.')
    return value

@ideas_bp.get('/',strict_slashes=False)
def workspace():
    return success_response(service.workspace(request.args.get('month') or None))

@ideas_bp.post('/refresh')
def refresh():
    return success_response({'sources':service.refresh()})

@ideas_bp.post('/publications')
def publication():
    return success_response(service.add_publication(body()),201)

@ideas_bp.post('/ideas')
def create_idea():
    return success_response(service.save_idea(body()),201)

@ideas_bp.put('/ideas/<int:idea_id>')
def update_idea(idea_id):
    return success_response(service.save_idea(body(),idea_id))

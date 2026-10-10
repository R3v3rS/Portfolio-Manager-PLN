from flask import Blueprint, request
from api.exceptions import ValidationError
from api.response import success_response
from investment_goals_service import workspace, save_goal, archive_goal
from database import get_db
from api.exceptions import NotFoundError

goals_bp = Blueprint('investment_goals', __name__)


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError('Nieprawidłowe dane celu.')
    return data


@goals_bp.get('/', strict_slashes=False)
def list_goals():
    return success_response(workspace())


@goals_bp.get('/<int:goal_id>/results')
def get_goal_results(goal_id):
    from actual_results_service import analyze
    db = get_db()
    if not db.execute('SELECT id FROM investment_goals WHERE id=?', (goal_id,)).fetchone():
        raise NotFoundError('Cel nie istnieje.')
    ids = [row['portfolio_id'] for row in db.execute('SELECT portfolio_id FROM investment_goal_portfolios WHERE goal_id=?', (goal_id,))]
    return success_response(analyze(ids, request.args.get('from'), request.args.get('to')))


@goals_bp.post('/', strict_slashes=False)
def create_goal():
    return success_response(save_goal(body()), status=201)


@goals_bp.put('/<int:goal_id>')
def update_goal(goal_id):
    return success_response(save_goal(body(), goal_id))


@goals_bp.put('/<int:goal_id>/archive')
def set_archive(goal_id):
    return success_response(archive_goal(goal_id, body().get('archived')))

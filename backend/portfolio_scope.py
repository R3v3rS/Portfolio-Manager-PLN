"""Resolve an account or child account to the shared transaction/holdings scope."""

from api.exceptions import NotFoundError, ValidationError


def resolve_portfolio_scope(db, portfolio_id, sub_portfolio_id=None):
    portfolio = db.execute(
        'SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)
    ).fetchone()
    if not portfolio:
        raise NotFoundError('Portfel nie istnieje.')
    if portfolio['parent_portfolio_id']:
        if sub_portfolio_id not in (None, portfolio['id']):
            raise ValidationError('Wybrany podportfel nie należy do tego portfela.')
        return portfolio['parent_portfolio_id'], portfolio['id']
    if sub_portfolio_id is not None:
        child = db.execute(
            'SELECT id FROM portfolios WHERE id = ? AND parent_portfolio_id = ?',
            (sub_portfolio_id, portfolio_id),
        ).fetchone()
        if not child:
            raise ValidationError('Wybrany podportfel nie należy do tego portfela.')
    return portfolio_id, sub_portfolio_id

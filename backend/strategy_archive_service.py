"""Close a strategy atomically, returning custody to its parent and freezing its report."""
import json
from datetime import datetime
from uuid import uuid4
from database import get_db
from api.exceptions import ValidationError


def snapshot(portfolio_id, key):
    from flask import has_app_context
    if not has_app_context(): return None
    db=get_db()
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='portfolio_archive_snapshots'").fetchone(): return None
    row=db.execute('SELECT s.data FROM portfolio_archive_snapshots s JOIN portfolios p ON p.id=s.portfolio_id WHERE s.portfolio_id=? AND p.is_archived=1',(portfolio_id,)).fetchone()
    return json.loads(row['data']).get(key) if row else None


def archive(portfolio_id):
    from portfolio_valuation_service import PortfolioValuationService as Value
    from portfolio_history_service import PortfolioHistoryService as History
    from asset_transfer_service import transfer
    from portfolio_service import PortfolioService
    from actual_results_service import analyze
    db=get_db()
    try:
        child=db.execute('SELECT * FROM portfolios WHERE id=?',(portfolio_id,)).fetchone()
        if not child or not child['parent_portfolio_id']:
            raise ValidationError('Archiwizować można podkonto strategii.')
        if child['is_archived']:
            return True
        parent=child['parent_portfolio_id']
        root=db.execute('SELECT * FROM portfolios WHERE id=?',(parent,)).fetchone()
        if not root or root['is_archived'] or child['account_type'] not in ('STANDARD','IKE','IKZE'):
            raise ValidationError('Ta operacja jest dostępna dla strategii w aktywnym portfelu akcji.')
        def state():
            return (tuple(db.execute('SELECT * FROM portfolios WHERE id=?',(portfolio_id,)).fetchone()),
                    [tuple(r) for r in db.execute('SELECT id,ticker,quantity,total_cost,currency FROM holdings WHERE portfolio_id=? AND sub_portfolio_id=? ORDER BY id',(parent,portfolio_id))],
                    [tuple(r) for r in db.execute('SELECT * FROM transactions WHERE portfolio_id=? AND sub_portfolio_id=? ORDER BY id',(parent,portfolio_id))])
        expected=state()
        holdings=Value.get_holdings(portfolio_id,cached_prices_only=True)
        if any(h.get('current_price_pln') is None or h['current_price_pln']<=0 for h in holdings):
            raise ValidationError('Brakuje wyceny pozycji. Wpisz cenę ręcznie przed archiwizacją, żeby prawidłowo zamknąć wynik strategii.')
        History.clear_cache(portfolio_id)
        frozen={'value':Value.get_portfolio_value(portfolio_id,cached_prices_only=True),
                'holdings':holdings,
                'metrics':History._calculate_historical_metrics(portfolio_id),
                'daily_profit':History.get_portfolio_profit_history_daily(portfolio_id,365),
                'daily_value':History.get_portfolio_value_history_daily(portfolio_id,365),
                'matrix':History.get_performance_matrix(portfolio_id),
                'results':analyze([portfolio_id])}
        db.execute('BEGIN IMMEDIATE')
        if state()!=expected: raise ValidationError('Podkonto zmieniło się podczas przygotowania archiwum. Odśwież widok i spróbuj ponownie.')
        root=db.execute('SELECT * FROM portfolios WHERE id=?',(parent,)).fetchone()
        if not root or root['is_archived']: raise ValidationError('Główny portfel nie jest aktywny.')
        stamp=datetime.now().isoformat(sep=' ',timespec='seconds')
        for h in holdings:
            transfer(dict(portfolio_id=parent,source_id=portfolio_id,target_id=None,ticker=h['ticker'],quantity=h['quantity'],expected_quantity=h['quantity'],price_pln=h['current_price_pln']),manage_transaction=False,stamp=stamp)
        cash=float(child['current_cash'] or 0)
        if cash<0: raise ValidationError('Podkonto ma ujemną gotówkę. Rozlicz ją przed archiwizacją.')
        if cash:
            transfer_id='archive-cash:'+str(uuid4())
            for sub,kind in ((portfolio_id,'WITHDRAW'),(None,'DEPOSIT')):
                db.execute("INSERT INTO transactions(portfolio_id,sub_portfolio_id,ticker,type,quantity,price,total_value,date,transfer_id) VALUES(?,?,'CASH',?,1,?,?,?,?)",(parent,sub,kind,cash,cash,stamp,transfer_id))
            db.execute('UPDATE portfolios SET current_cash=current_cash+? WHERE id=?',(cash,parent))
        db.execute('UPDATE portfolios SET current_cash=0,is_archived=1,archived_at=? WHERE id=?',(stamp,portfolio_id))
        db.execute('INSERT INTO portfolio_archive_snapshots(portfolio_id,archived_at,data) VALUES(?,?,?)',(portfolio_id,stamp,json.dumps(frozen,ensure_ascii=False,allow_nan=False)))
        for table in ('portfolio_history_cache','analytics_cache'):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone(): db.execute('DELETE FROM '+table)
        db.commit()
    except Exception:
        db.rollback()
        PortfolioService.clear_cache(portfolio_id)
        raise
    PortfolioService.clear_cache(parent)
    PortfolioService.clear_cache(portfolio_id)
    return True

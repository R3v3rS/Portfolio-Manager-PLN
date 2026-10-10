"""One-time consolidation, callable only by the local maintenance script."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal as D


def consolidate(db, pid):
    parent=db.execute('SELECT * FROM portfolios WHERE id=?',(pid,)).fetchone()
    assert parent and parent['account_type']=='IKE' and not parent['parent_portfolio_id']
    children=[dict(r) for r in db.execute('SELECT * FROM portfolios WHERE parent_portfolio_id=? AND is_archived=0',(pid,))]
    assert children,'No active children to consolidate'
    ids=[pid]+[c['id'] for c in children];marks=','.join('?' for _ in ids)
    assert not db.execute(f"SELECT 1 FROM transactions WHERE portfolio_id IN ({marks}) AND type IN ('ASSET_IN','ASSET_OUT')",ids).fetchone(),'Consolidation of existing asset transfers requires a separate migration'
    holdings=[dict(r) for r in db.execute(f'SELECT * FROM holdings WHERE portfolio_id IN ({marks})',ids)]
    assert all((h['currency'] or 'PLN')=='PLN' for h in holdings),'Foreign-currency basis needs separate reconciliation'
    before_qty=defaultdict(float)
    for h in holdings:before_qty[h['ticker']]+=float(h['quantity'])
    before_cash=D(str(parent['current_cash']))+sum((D(str(c['current_cash'])) for c in children),D(0))
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute(f'UPDATE transactions SET portfolio_id=?,sub_portfolio_id=NULL WHERE portfolio_id IN ({marks})',[pid,*ids])
        rows=db.execute('SELECT * FROM transactions WHERE portfolio_id=? ORDER BY date,id',(pid,)).fetchall()
        positions={};cash=D(0);realized=D(0)
        for t in rows:
            a=D(str(t['total_value']));n=D(str(t['quantity']));kind=t['type'];ticker=t['ticker']
            cash+=a if kind in ('DEPOSIT','SELL','DIVIDEND','INTEREST') else -a if kind in ('BUY','WITHDRAW') else D(0)
            q,c=positions.get(ticker,(D(0),D(0)))
            if kind=='BUY':positions[ticker]=(q+n,c+a)
            elif kind=='SELL':
                assert q+D('0.000001')>=n, f'Insufficient quantity in transaction {t["id"]}'
                cost=c*n/q;profit=a-cost;realized+=profit
                positions[ticker]=(max(D(0),q-n),c-cost if q-n>D('.00000001') else D(0))
                db.execute('UPDATE transactions SET realized_profit=?,realized_profit_pln=? WHERE id=?',(float(profit),float(profit),t['id']))
        assert abs(cash-before_cash)<D('.005'),f'Cash mismatch {cash} != {before_cash}'
        after_qty={t:float(q) for t,(q,c) in positions.items() if q>D('.000001')}
        assert all(abs(before_qty[t]-after_qty.get(t,0))<1e-6 for t in set(before_qty)|set(after_qty)),'Quantity mismatch'
        db.execute(f'DELETE FROM holdings WHERE portfolio_id IN ({marks})',ids)
        for ticker,(q,c) in positions.items():
            if q<D('.000001'):continue
            template=next(h for h in holdings if h['ticker']==ticker)
            values={k:v for k,v in template.items() if k!='id'}
            values.update(portfolio_id=pid,sub_portfolio_id=None,quantity=float(q),total_cost=float(c),average_buy_price=float(c/q),avg_buy_price_native=float(c/q),avg_buy_fx_rate=1)
            cols=','.join(values);db.execute(f"INSERT INTO holdings({cols}) VALUES({','.join('?' for _ in values)})",list(values.values()))
        db.execute(f'DELETE FROM dividends WHERE portfolio_id IN ({marks})',ids)
        for t in rows:
            if t['type']=='DIVIDEND':db.execute('INSERT INTO dividends(portfolio_id,sub_portfolio_id,ticker,date,amount) VALUES(?,NULL,?,?,?)',(pid,t['ticker'],t['date'][:10],t['total_value']))
        db.execute('UPDATE portfolios SET current_cash=? WHERE id=?',(float(cash),pid))
        for child in children:
            db.execute('UPDATE portfolios SET current_cash=0,is_archived=1,archived_at=? WHERE id=?',(datetime.now().isoformat(),child['id']))
            for goal in db.execute('SELECT goal_id FROM investment_goal_portfolios WHERE portfolio_id=?',(child['id'],)).fetchall():
                db.execute('INSERT OR IGNORE INTO investment_goal_portfolios(goal_id,portfolio_id) VALUES(?,?)',(goal['goal_id'],pid))
            db.execute('DELETE FROM investment_goal_portfolios WHERE portfolio_id=?',(child['id'],))
        for table in ('portfolio_history_cache','analytics_cache'):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():db.execute('DELETE FROM '+table)
        db.commit()
        return {'parent_id':pid,'archived_children':[c['id'] for c in children],'cash':float(cash),'positions':after_qty,'transactions':len(rows),'realized_profit':float(realized)}
    except Exception:
        db.rollback();raise

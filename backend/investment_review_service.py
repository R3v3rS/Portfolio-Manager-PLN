"""Instrument event history and strategies compared without double-counting custody."""
from database import get_db
from api.exceptions import NotFoundError,ValidationError
from portfolio_valuation_service import PortfolioValuationService as Value
from strategy_archive_service import snapshot


def events(portfolio_id,ticker=None):
    db=get_db()
    p=db.execute('SELECT * FROM portfolios WHERE id=?',(portfolio_id,)).fetchone()
    if not p: raise NotFoundError('Portfel nie istnieje.')
    parent=p['parent_portfolio_id'] or portfolio_id
    sql='SELECT t.*,s.name AS strategy_name FROM transactions t LEFT JOIN portfolios s ON s.id=t.sub_portfolio_id WHERE t.portfolio_id=?'
    args=[parent]
    if p['parent_portfolio_id']: sql+=' AND t.sub_portfolio_id=?';args.append(portfolio_id)
    if ticker: sql+=' AND t.ticker=?';args.append(ticker)
    sql+=" ORDER BY date(t.date), CASE WHEN t.type='SELL' AND length(t.date)=10 THEN '23:59:59' ELSE substr(t.date,12) END,t.id"
    rows=[dict(r) for r in db.execute(sql,args)]
    if p['parent_portfolio_id']:
        from asset_transfer_service import strategy_basis
        _,profits=strategy_basis(db,parent,portfolio_id)
        for r in rows:
            if r['type']=='SELL': r['realized_profit']=profits.get(r['id'],r['realized_profit'])
    return dict(p),rows


def instrument(portfolio_id,ticker):
    if not ticker or ticker=='CASH' or len(ticker)>80: raise ValidationError('Wybierz instrument.')
    p,rows=events(portfolio_id,ticker)
    if not rows: raise NotFoundError('Brak historii tego instrumentu w portfelu.')
    holding=next((h for h in Value.get_holdings(portfolio_id,cached_prices_only=True) if h['ticker']==ticker),None)
    quantity=0.;flow=0.;dividends=0.;timeline=[]
    for r in rows:
        kind=r['type'];amount=float(r['total_value']);qty=float(r['quantity'])
        if kind in ('BUY','ASSET_IN'): quantity+=qty;flow-=amount
        elif kind in ('SELL','ASSET_OUT'):quantity-=qty;flow+=amount
        elif kind=='DIVIDEND':dividends+=amount
        timeline.append({k:r[k] for k in ('id','date','type','quantity','price','total_value','realized_profit','strategy_name','transfer_id') }|{'remaining_quantity':round(quantity,8)})
    current=holding.get('current_value') if holding else 0.
    meta=get_db().execute('SELECT company_name FROM asset_metadata WHERE ticker=?',(ticker,)).fetchone()
    return {'ticker':ticker,'company_name':holding.get('company_name') if holding else meta['company_name'] if meta else None,'quantity':round(quantity,8),'current_value':current,
            'total_result':None if current is None else round(current+flow+dividends,2),'dividends':round(dividends,2),
            'realized_profit':round(sum(float(r['realized_profit'] or 0) for r in rows if r['type']=='SELL'),2),
            'price_basis':holding.get('price_basis') if holding else None,'archived':bool(p['is_archived']),'events':timeline}


def strategies(portfolio_id):
    p,_=events(portfolio_id)
    parent=p['parent_portfolio_id'] or portfolio_id
    db=get_db();rows=[]
    for child in db.execute('SELECT * FROM portfolios WHERE parent_portfolio_id=? ORDER BY is_archived,name,id',(parent,)):
        pid=child['id'];frozen=snapshot(pid,'value')
        value=frozen or ({'portfolio_value':None,'total_result':None,'total_result_percent':None,'xirr_percent':None,'valuation_status':'legacy_archive'} if child['is_archived'] else Value.get_portfolio_value(pid,cached_prices_only=True))
        _,tx=events(pid)
        dates=[str(r['date'])[:10] for r in tx if r['type'] in ('DEPOSIT','ASSET_IN','BUY')]
        first=min(dates) if dates else None
        incoming=[r for r in tx if r['type'] in ('DEPOSIT','ASSET_IN')]
        starting=sum(float(r['total_value']) for r in incoming if str(r['date'])[:10]==first)
        added=sum(float(r['total_value']) for r in incoming if str(r['date'])[:10]!=first)
        rows.append({'id':pid,'name':child['name'],'archived':bool(child['is_archived']),'frozen':frozen is not None,
                     'started_at':first,'closed_at':child['archived_at'],'starting_capital':round(starting,2),'additional_capital':round(added,2),
                     'value':value['portfolio_value'],'result':value['total_result'],'return_percent':value['total_result_percent'],
                     'valuation_status':value.get('valuation_status'),'xirr_percent':value.get('xirr_percent')})
    return {'parent_id':parent,'items':rows,'total':Value.get_portfolio_value(parent,cached_prices_only=True)}

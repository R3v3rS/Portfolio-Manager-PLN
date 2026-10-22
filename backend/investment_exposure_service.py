"""Partial look-through with explicit unknown coverage and source dates."""
import json
from collections import defaultdict
from datetime import date
from urllib.parse import urlsplit
from api.exceptions import ApiError, ValidationError
from database import get_db
from investment_ai_provider import number, now
from investment_allocation_service import symbol
from investment_ai_context import portfolio
from portfolio_valuation_service import PortfolioValuationService as Value

def save_composition(ticker,data,source_kind='manual'):
    symbol(ticker);url=data.get('source_url','')
    try:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise ValueError()
    except (TypeError,ValueError):raise ValidationError('Podaj link HTTPS do źródła składu funduszu.') from None
    day=data.get('source_date') or None
    if source_kind=='manual' and not day:raise ValidationError('Podaj datę składu ze źródła.')
    if day:
        try:
            d=date.fromisoformat(day)
            if d>date.today() or d<date(2000,1,1):raise ValueError()
        except (TypeError,ValueError):raise ValidationError('Podaj poprawną datę składu funduszu.') from None
    items=data.get('constituents')
    if not isinstance(items,list) or not 1<=len(items)<=2000:raise ValidationError('Podaj od 1 do 2000 pozycji składu.')
    rows=[];seen=set()
    for item in items:
        if not isinstance(item,dict):raise ValidationError('Nieprawidłowy skład funduszu.')
        key=symbol(item.get('ticker',''))
        if key==ticker or key in seen:raise ValidationError('Skład nie może zawierać funduszu ani powtórzeń.')
        seen.add(key);rows.append(dict(ticker=key,percent=number(item.get('percent'),'Udział składnika',.000001,100)))
    if sum(r['percent'] for r in rows)>100.01:raise ValidationError('Suma udziałów przekracza 100%.')
    db=get_db();db.execute('INSERT INTO investment_fund_compositions(ticker,constituents,source_url,source_date,retrieved_at,source_kind) VALUES(?,?,?,?,?,?) ON CONFLICT(ticker) DO UPDATE SET constituents=excluded.constituents,source_url=excluded.source_url,source_date=excluded.source_date,retrieved_at=excluded.retrieved_at,source_kind=excluded.source_kind',
                         (ticker,json.dumps(rows),url,day,now(),source_kind));db.commit()
    return {'ticker':ticker,'coverage_percent':sum(r['percent'] for r in rows)}

def refresh(ticker):
    symbol(ticker)
    try:
        import yfinance as yf
        data=yf.Ticker(ticker).funds_data.top_holdings
        if data is None or data.empty or 'Holding Percent' not in data.columns:raise ValueError()
        rows=[dict(ticker=str(key).upper(),percent=float(row['Holding Percent'])*100) for key,row in data.iterrows()]
    except Exception:
        raise ApiError('fund_composition_unavailable','Dostawca nie udostępnił składu. Możesz wkleić udziały z dokumentu emitenta.',status=502) from None
    # Retrieval time is not the underlying holdings date. Never claim these are current.
    return save_composition(ticker,dict(constituents=rows,source_url=f'https://finance.yahoo.com/quote/{ticker}/holdings/',source_date=None),'yahoo')

def exposure(pid,include_children=True):
    p=portfolio(pid)
    if p['account_type'] not in ('STANDARD','IKE','IKZE'):return dict(items=[],funds=[],coverage_percent=None,unknown_value=0,warnings=['Analiza dotyczy akcji i ETF-ów.'])
    db=get_db();holdings=Value.get_holdings(pid,cached_prices_only=True,aggregate=include_children)
    configs={r['ticker']:{**dict(r),'constituents':json.loads(r['constituents'])} for r in db.execute('SELECT * FROM investment_fund_compositions')}
    exposures=defaultdict(lambda:dict(value=0.,sources=[]));funds=[];total=0.;known=0.;missing=[]
    for h in holdings:
        if h['quantity']<=0:continue
        ticker=h['ticker'];value=h.get('current_value')
        if value is None:missing.append(ticker);continue
        total+=value
        cfg=configs.get(ticker)
        name=str(h.get('company_name','')).upper()
        is_fund=cfg is not None or ticker.startswith('ETF') or any(word in name for word in ('ETF','UCITS','INDEX FUND')) or str(h.get('sector','')).lower() in ('etf','fund')
        if not is_fund:
            exposures[ticker]['value']+=value;exposures[ticker]['sources'].append({'instrument':ticker,'value':value,'direct':True});known+=value
            continue
        coverage=sum(r['percent'] for r in cfg['constituents']) if cfg else 0
        funds.append(dict(ticker=ticker,coverage_percent=coverage,source_date=cfg['source_date'] if cfg else None,
                          retrieved_at=cfg['retrieved_at'] if cfg else None,source_url=cfg['source_url'] if cfg else None,
                          stale=not cfg or not cfg['source_date'] or (date.today()-date.fromisoformat(cfg['source_date'])).days>90))
        if cfg:
            for row in cfg['constituents']:
                part=value*row['percent']/100;known+=part
                exposures[row['ticker']]['value']+=part
                exposures[row['ticker']]['sources'].append({'instrument':ticker,'value':part,'direct':False})
    items=[dict(ticker=k,value=round(v['value'],2),weight_percent=v['value']/total*100 if total else None,
                sources=v['sources'],overlap=len({s['instrument'] for s in v['sources']})>1) for k,v in exposures.items()]
    warnings=['Skład może być częściowy; nieznana część nie jest rozdzielana. Łączymy identyczne tickery, bez zgadywania odpowiedników giełdowych.']
    warnings.append('Fundusze rozpoznajemy po nazwie, sektorze lub zapisanym składzie. Uzupełnij skład nierozpoznanego funduszu. Analiza rozwija jeden poziom składu.')
    if missing:warnings.append('Brak wyceny: '+', '.join(missing)+'. Udziały obejmują wycenioną część.')
    if any(f['stale'] for f in funds):warnings.append('Część składów jest starsza niż 90 dni lub dostawca nie podał ich daty.')
    return dict(items=sorted(items,key=lambda r:-r['value']),funds=funds,coverage_percent=known/total*100 if total else None,
                unknown_value=max(0,round(total-known,2)),missing_tickers=missing,warnings=warnings,total=round(total,2))

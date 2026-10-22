"""Target allocations and contribution-only simulations. Never book trades."""
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from api.exceptions import ApiError, ValidationError
from database import get_db
from investment_ai_context import portfolio, valuation
from investment_ai_provider import number, now
from portfolio_valuation_service import PortfolioValuationService as Value

def symbol(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^=_-]{0,39}',value):
        raise ValidationError('Podaj poprawny symbol instrumentu.')
    return value

def get_plan(pid):
    p=portfolio(pid); db=get_db()
    row=db.execute('SELECT * FROM investment_strategy_plans WHERE portfolio_id=?',(pid,)).fetchone()
    plan=json.loads(row['value']) if row else dict(goal='',horizon='',constraints='',mode='INSTRUMENT',targets=[])
    held=Value.get_holdings(pid,cached_prices_only=True) if p['account_type'] in ('IKE','IKZE','STANDARD') else []
    children=[dict(r) for r in db.execute('SELECT id,name FROM portfolios WHERE parent_portfolio_id=? AND COALESCE(is_archived,0)=0',(pid,))]
    return dict(plan=plan,version=row['version'] if row else 0,portfolio_id=pid,archived=bool(p['is_archived']),
                instruments=sorted({h['ticker'] for h in held if h['quantity']>0}),children=children,account_type=p['account_type'])

def validate(pid,data):
    p=portfolio(pid)
    if p['is_archived']:raise ValidationError('Nie zmieniaj planu zarchiwizowanej strategii.')
    mode=data.get('mode','INSTRUMENT')
    if mode not in ('INSTRUMENT','STRATEGY'):raise ValidationError('Wybierz plan instrumentów albo strategii.')
    if mode=='STRATEGY' and p['parent_portfolio_id']:raise ValidationError('Plan strategii utwórz na portfelu głównym.')
    result={'mode':mode}
    for key in ('goal','horizon','constraints'):
        v=data.get(key,'')
        if not isinstance(v,str) or len(v)>2000:raise ValidationError('Opis planu może mieć do 2000 znaków.')
        result[key]=v.strip()
    targets=data.get('targets',[])
    if not isinstance(targets,list) or len(targets)>100:raise ValidationError('Plan może mieć do 100 pozycji.')
    allowed={'OWN'}|{str(r['id']) for r in get_db().execute('SELECT id FROM portfolios WHERE parent_portfolio_id=? AND COALESCE(is_archived,0)=0',(pid,))}
    output=[];seen=set()
    for t in targets:
        if not isinstance(t,dict):raise ValidationError('Nieprawidłowa pozycja planu.')
        key=t.get('key','')
        if mode=='STRATEGY' and key not in allowed:raise ValidationError('Wybrana strategia jest nieaktywna lub należy do innego portfela.')
        if mode=='INSTRUMENT':symbol(key)
        if key in seen:raise ValidationError('Pozycje planu nie mogą się powtarzać.')
        seen.add(key);output.append(dict(key=key,percent=round(number(t.get('percent'),'Udział',0,100),2)))
    if output and abs(sum(t['percent'] for t in output)-100)>.001:raise ValidationError('Udziały muszą sumować się do 100%. Uwzględnij również gotówkę.')
    result['targets']=output
    return result

def save_plan(pid,data):
    value=validate(pid,data);db=get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        current=get_plan(pid)
        if type(data.get('version')) is not int or data['version']!=current['version']:
            raise ApiError('investment_plan_changed','Plan zmienił się. Wczytaj ponownie.',status=409)
        db.execute('INSERT INTO investment_strategy_plans(portfolio_id,value,version,updated_at) VALUES(?,?,?,?) ON CONFLICT(portfolio_id) DO UPDATE SET value=excluded.value,version=excluded.version,updated_at=excluded.updated_at',
                   (pid,json.dumps(value,ensure_ascii=False),current['version']+1,now()))
        db.commit()
    except Exception:db.rollback();raise
    return get_plan(pid)

def simulate(pid,data):
    profile=get_plan(pid);plan=profile['plan'];p=portfolio(pid)
    if p['is_archived']:raise ValidationError('Wybierz aktywny portfel.')
    contribution=number(data.get('contribution'),'Nowa wpłata',0,1_000_000_000)
    if not plan['targets']:raise ValidationError('Zapisz docelowe udziały przed symulacją.')
    # Also reject stale strategy destinations after an archive.
    validate(pid,plan)
    value=valuation(pid); warnings=value.get('valuation_warnings',[])
    if value.get('portfolio_value') is None:raise ValidationError('Uzupełnij brakujące wyceny przed symulacją. Cena zakupu nie zastępuje kursu.')
    current={};labels={};cash_key='CASH' if plan['mode']=='INSTRUMENT' else 'OWN'
    if plan['mode']=='INSTRUMENT':
        if p['account_type'] not in ('STANDARD','IKE','IKZE'):raise ValidationError('Symulacja instrumentów jest dostępna dla portfeli akcyjnych. Założenia strategii możesz zapisać dla każdego konta.')
        for h in Value.get_holdings(pid,cached_prices_only=True):
            if h['quantity']<=0:continue
            if h.get('current_value') is None:raise ValidationError('Brakuje ceny jednej z pozycji.')
            current[h['ticker']]=current.get(h['ticker'],0)+h['current_value'];labels[h['ticker']]=h.get('company_name') or h['ticker']
        current['CASH']=value['cash_value'];labels['CASH']='Gotówka'
    else:
        own=valuation(pid,False)
        if own.get('portfolio_value') is None:raise ValidationError('Niepełna wycena części głównej.')
        current['OWN']=own['portfolio_value'];labels['OWN']='Część główna'
        for child in profile['children']:
            v=valuation(child['id'])
            if v.get('portfolio_value') is None:raise ValidationError('Niepełna wycena strategii.')
            current[str(child['id'])]=v['portfolio_value'];labels[str(child['id'])]=child['name']
    if any(v<0 for v in current.values()):raise ValidationError('Symulacja wymaga nieujemnych wartości i gotówki.')
    cents=lambda n:int((Decimal(str(n))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    current={k:cents(v) for k,v in current.items()};budget=cents(contribution);total=sum(current.values())+budget
    target={t['key']:t['percent'] for t in plan['targets']};keys=list(dict.fromkeys([*current,*target]))
    # Deficit-proportional contributions, capped at each target; never propose a sale.
    deficits={k:max(0,cents(total/100*target.get(k,0)/100)-current.get(k,0)) for k in keys if k!=cash_key}
    deploy=min(budget,sum(deficits.values()));weights=sum(deficits.values())
    adds={k:(deploy*v//weights if weights else 0) for k,v in deficits.items()}
    remaining=deploy-sum(adds.values())
    for k in sorted(adds,key=lambda k:-(deploy*deficits[k]%weights if weights else 0)):
        if remaining and adds[k]<deficits[k]:adds[k]+=1;remaining-=1
    adds[cash_key]=budget-sum(adds.values())
    rows=[]
    for k in dict.fromkeys([*keys,cash_key]):
        before=current.get(k,0);added=adds.get(k,0);after=before+added
        rows.append(dict(key=k,label=labels.get(k,k),target_percent=target.get(k,0),before=before/100,contribution=added/100,
                         after=after/100,after_percent=after/total*100 if total else 0,
                         difference=after/total*100-target.get(k,0) if total else -target.get(k,0)))
    return dict(rows=rows,total=total/100,contribution=budget/100,warnings=warnings,
                note='Rozdział wyłącznie nowej wpłaty; obecna gotówka i pozycje pozostają. Kwoty orientacyjne, bez zleceń, podatków, prowizji i zaokrąglania do liczby akcji.',version=profile['version'])

"""Same valuation/results as portfolio views; snapshots never refresh market data."""
import json
import math
from datetime import date
from urllib.parse import quote

from api.exceptions import NotFoundError, ValidationError
from database import get_db
from actual_results_service import analyze, analysis_dates
from portfolio_chart_service import attribution
from portfolio_valuation_service import PortfolioValuationService as Value
from investment_ai_provider import now


def clean(value):
    if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def portfolio(pid):
    row = get_db().execute('SELECT * FROM portfolios WHERE id=?', (pid,)).fetchone()
    if not row: raise NotFoundError('Portfel nie istnieje.')
    return dict(row)


def valuation(pid, include_children=True):
    p = portfolio(pid)
    if include_children or p['parent_portfolio_id'] or p['is_archived']:
        return Value.get_portfolio_value(pid, cached_prices_only=True)
    return Value._validated_result(Value._calculate_single_portfolio_value(p, cached_prices_only=True))


def build(pid, include_children=True, start=None, end=None):
    if type(include_children) is not bool: raise ValidationError('Wybierz zakres portfela.')
    p = portfolio(pid); db = get_db()
    if p['is_archived']: raise ValidationError('Archiwum ma zapisany wynik. Wybierz aktywny portfel do nowej analizy.')
    first, last = analysis_dates(start or date.today().replace(day=1).isoformat(), end)
    value = valuation(pid, include_children)
    equity = p['account_type'] in ('STANDARD', 'IKE', 'IKZE')
    holdings = Value.get_holdings(pid, aggregate=include_children, cached_prices_only=True) if equity else []
    fields = ('ticker','company_name','currency','quantity','total_cost','current_price','current_price_pln',
              'current_value','estimated_current_value','profit_loss','profit_loss_percent','sector','price_basis',
              'price_last_updated_at','fx_last_updated_at','fx_rate_used','valuation_status','valuation_warnings')
    positions = [{k: h.get(k) for k in fields} for h in holdings if h['quantity'] > 0]
    results = analyze([pid], first.isoformat(), last.isoformat(), own_only=not include_children)
    contributors = attribution(pid, first, last, own_only=not include_children, cached_only=True) if equity else {'items':[], 'status':'special_account'}
    ids = [pid] + ([r['id'] for r in db.execute('SELECT id FROM portfolios WHERE parent_portfolio_id=? AND COALESCE(is_archived,0)=0', (pid,))] if include_children else [])
    marks = ','.join('?' for _ in ids)
    journals = [dict(r) for r in db.execute(f'SELECT id,title,ticker,thesis,risks,invalidation,exit_plan,review_date FROM investor_journal WHERE portfolio_id IN ({marks}) AND is_archived=0 ORDER BY entry_date DESC LIMIT 20', ids)]
    mandates = [dict(r) for r in db.execute(f'SELECT portfolio_id,value,version FROM investment_strategy_plans WHERE portfolio_id IN ({marks})', ids)]
    for row in mandates: row['value'] = json.loads(row['value'])
    sources = [dict(id='valuation', label='Bieżąca wycena portfela', href=f'/portfolio/{pid}?tab=holdings', data=value),
               dict(id='results', label=f'Wyniki {first} – {last}', href=f'/portfolio/{pid}?tab=results', data=results),
               dict(id='attribution', label='Wkład instrumentów w wynik', href=f'/portfolio/{pid}?tab=results', data=contributors),
               dict(id='strategy', label='Zapisane założenia i udziały', href=f'/portfolio/{pid}?tab=analytics', data=mandates)]
    sources.extend(dict(id=f'position:{h["ticker"]}', label=h['ticker'], href=f'/radar?ticker={quote(h["ticker"])}', data=h) for h in positions)
    sources.extend(dict(id=f'journal:{j["id"]}', label=j['title'], href=f'/journal?portfolio={pid}', data=j) for j in journals)
    held={h['ticker'] for h in positions}
    materials=[dict(r) for r in db.execute('''SELECT i.ticker,i.thesis,i.risks,i.evidence,i.opinion,p.title,p.url,p.published_on
        FROM research_ideas i JOIN research_publications p ON p.id=i.publication_id ORDER BY p.published_on DESC''') if r['ticker'] in held][:20]
    sources.append(dict(id='materials',label='Zatwierdzone analizy materiałów',href='/ideas',data=materials))
    if equity:
        from investment_exposure_service import exposure
        sources.append(dict(id='exposure',label='Znany skład funduszy',href=f'/portfolio/{pid}?tab=analytics&analysis=exposure',data=exposure(pid,include_children)))
    special = None
    if p['account_type'] == 'BONDS':
        from bond_service import BondService
        special = BondService.get_bonds(pid)
    elif p['account_type'] == 'PPK':
        from modules.ppk.ppk_service import PPKService
        special = {'quote': PPKService.get_cached_price(), 'summary': value}
    elif p['account_type'] == 'SAVINGS':
        special = {k: p.get(k) for k in ('current_cash','savings_rate','last_interest_date')}
    if special is not None: sources.append(dict(id='account_details', label='Dane konta i metoda wyceny', href=f'/portfolio/{pid}', data=special))
    valuation_warnings=value.get('valuation_warnings') or []
    result_warnings=[w.replace('prognoza celu jest wstrzymana','wynik okresu wymaga aktualnej wyceny') for w in results.get('warnings',[])
                     if not ('nieaktualna cena' in w and any(v.startswith(w.split(':')[0]+':') for v in valuation_warnings))]
    warnings = list(dict.fromkeys(valuation_warnings + result_warnings))
    if contributors.get('missing_tickers'): warnings.append('Niepełny wkład spółek: '+', '.join(contributors['missing_tickers']))
    if last != date.today(): warnings.append('Wyniki dotyczą wybranego okresu. Pozycje i wycena bieżąca pokazują stan zapisany dzisiaj.')
    return clean(dict(portfolio_id=pid, name=p['name'], account_type=p['account_type'], include_subportfolios=include_children,
                      created_at=now(), start=first.isoformat(), end=last.isoformat(), value=value, positions=positions,
                      results=results, contributors=contributors, warnings=warnings, sources=sources,
                      special=special, subportfolios_count=len(ids)-1))


def facts(snapshot):
    def amount(v): return 'brak pełnej wyceny' if v is None else f'{v:,.2f} PLN'.replace(',', ' ').replace('.', ',')
    result = snapshot['results']; value = snapshot['value']
    changed = [dict(text=f'Wynik okresu: {amount(result.get("profit"))}. Wpłaty netto: {amount(result.get("net_deposits"))}.', source_ids=['results'])]
    why = [dict(text=f'Dywidendy: {amount(result.get("dividends"))}; wynik sprzedaży: {amount(result.get("realized_profit"))}.', source_ids=['results'])]
    for item in sorted(snapshot['contributors'].get('items', []), key=lambda i: abs(i['value']), reverse=True)[:3]:
        why.append(dict(text=f'{item["ticker"]}: wkład w wynik {amount(item["value"])}.', source_ids=['attribution']))
    checks = [dict(text='Sprawdź założenia strategii i zapisz termin kolejnego przeglądu.', source_ids=['strategy'])]
    return dict(title='Podsumowanie zapisanych danych', changed=changed, why=why, check=checks,
                limitations=[dict(text=w, source_ids=['valuation','results']) for w in snapshot['warnings']] or
                             [dict(text='Podsumowanie wykorzystuje zapisane dane. Wynik historyczny nie jest prognozą.', source_ids=['results'])],
                valuation_status=value.get('valuation_status'), mode='data')

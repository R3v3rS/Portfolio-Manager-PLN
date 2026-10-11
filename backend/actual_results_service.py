"""Read-only results of recorded operations, with explicit valuation quality."""
import math
from collections import defaultdict
from datetime import date, timedelta

from api.exceptions import NotFoundError, ValidationError
from database import get_db
from investment_goals_service import _portfolios, _scope, _own_snapshot
from portfolio_history_service import PortfolioHistoryService as History
from portfolio_valuation_service import PortfolioValuationService


def analysis_dates(start=None, end=None):
    try:
        first = date.fromisoformat(start) if start else None
        last = date.fromisoformat(end) if end else date.today()
        if last > date.today() or last < date(2000, 1, 1) or (first and (first > last or first < date(2000, 1, 1))):
            raise ValueError()
        return first, last
    except (TypeError, ValueError):
        raise ValidationError('Podaj poprawny okres analizy w formacie YYYY-MM-DD, bez przyszłych dat.') from None


from investment_math import modified_dietz, money_weighted


def analyze(portfolio_ids, start=None, end=None):
    if len(portfolio_ids)==1:
        from strategy_archive_service import snapshot
        frozen=snapshot(portfolio_ids[0],'results')
        if frozen is not None: return frozen
    start, end = analysis_dates(start, end)
    db = get_db()
    portfolios = _portfolios()
    selected = set()
    for portfolio_id in portfolio_ids:
        if portfolio_id not in portfolios:
            raise NotFoundError('Przypisany portfel nie istnieje.')
        selected.update(_scope(portfolio_id, portfolios))
    if not selected:
        raise ValidationError('Brak aktywnych portfeli do analizy.')
    # Normalize legacy child rows and modern parent+sub rows to one owner.
    rows = [dict(row) for row in db.execute('SELECT * FROM transactions WHERE date(date)<=? ORDER BY date(date),id', (end.isoformat(),))
            if (row['sub_portfolio_id'] or row['portfolio_id']) in selected or row['portfolio_id'] in selected]
    for row in rows:
        row['day'] = History._to_date(row['date'])
    from asset_transfer_service import strategy_basis
    for owner in selected:
        if portfolios[owner]['parent_portfolio_id'] and portfolios[owner]['parent_portfolio_id'] not in selected:
            _,profits=strategy_basis(db,portfolios[owner]['parent_portfolio_id'],owner)
            for row in rows:
                if row['sub_portfolio_id']==owner and row['type']=='SELL':
                    row['realized_profit']=profits.get(row['id'],row['realized_profit'])
    # The same dated valuation models serve reports and investment goals.
    from special_account_results import build_special_model
    special_ids = {p for p in selected if portfolios[p]['account_type'] in ('PPK', 'BONDS')}
    models = [build_special_model(db, portfolios[p], end) for p in sorted(special_ids)]
    first_record = min([row['day'] for row in rows] + [m['first_record'] for m in models], default=end)
    start = start or first_record
    warnings = []
    unsupported = [portfolios[p]['name'] for p in selected if portfolios[p]['account_type'] not in ('STANDARD', 'IKE', 'IKZE', 'SAVINGS', 'PPK', 'BONDS')]
    if unsupported:
        warnings.append('Pełna historia wyników wymaga odrębnej wyceny tych kont: ' + ', '.join(unsupported) + '. Ich operacje i kapitał nie są mieszane z historią rachunków maklerskich.')
    # Only a complete, balanced pair inside this scope is an internal transfer.
    groups = defaultdict(list)
    for row in rows:
        if row['transfer_id']:
            groups[row['transfer_id']].append(row)
    internal = set()
    for pair in groups.values():
        if len(pair) == 2 and {r['type'] for r in pair} in ({'DEPOSIT', 'WITHDRAW'}, {'ASSET_IN', 'ASSET_OUT'}) and pair[0]['day'] == pair[1]['day'] and abs(float(pair[0]['total_value']) - float(pair[1]['total_value'])) < .005:
            internal.update(r['id'] for r in pair)
    external = [row for row in rows if row['type'] in ('DEPOSIT', 'WITHDRAW', 'ASSET_IN', 'ASSET_OUT') and row['id'] not in internal]
    flows = [(r['day'], float(r['total_value']) * (1 if r['type'] in ('DEPOSIT','ASSET_IN') else -1)) for r in external]
    # Transaction cash flows are already included above; add only unit purchases
    # recorded in the separate PPK ledger. Internal transfer pairs stay excluded.
    for p in special_ids:
        if portfolios[p]['account_type'] == 'PPK':
            flows.extend((History._to_date(r['date']), (float(r['employee_units'])+float(r['employer_units']))*float(r['price_per_unit']))
                         for r in db.execute('SELECT * FROM ppk_transactions WHERE portfolio_id=? AND date(date)<=?', (p,end.isoformat())))
    active = [r for r in rows if r['day'] >= start]
    period_flows = [(day, amount) for day, amount in flows if day >= start]
    deposits = sum(amount for day, amount in period_flows if amount > 0)
    withdrawals = -sum(amount for day, amount in period_flows if amount < 0)
    tickers = {r['ticker'] for r in rows if r['type'] in ('BUY', 'SELL', 'ASSET_IN', 'ASSET_OUT') and r['ticker'] != 'CASH'}
    currencies = {r['ticker']: r['currency'] for r in db.execute('SELECT ticker,currency FROM asset_metadata') if r['currency']}
    for row in db.execute('SELECT portfolio_id,sub_portfolio_id,ticker,currency FROM holdings'):
        if (row['sub_portfolio_id'] or row['portfolio_id']) in selected and row['currency']:
            currencies[row['ticker']] = row['currency']
    needed = tickers | {f'{str(currencies[t]).upper()}PLN=X' for t in tickers if currencies.get(t) and str(currencies[t]).upper() != 'PLN'}
    prices = defaultdict(dict)
    for row in db.execute('SELECT ticker,date,close_price FROM stock_prices WHERE date(date)<=? ORDER BY date(date)', (end.isoformat(),)):
        if row['ticker'] in needed and row['close_price'] and float(row['close_price']) > 0:
            prices[row['ticker']][History._to_date(row['date']).isoformat()] = float(row['close_price'])
    index = History._build_sorted_price_index(prices)

    def state(day, include_special=True):
        cash, quantities = 0.0, defaultdict(float)
        for row in rows:
            if row['day'] > day:
                break
            if not include_special and (row['sub_portfolio_id'] or row['portfolio_id']) in special_ids:
                continue
            cash += PortfolioValuationService.cash_delta(row)
            if row['type'] in ('BUY', 'SELL', 'ASSET_IN', 'ASSET_OUT'):
                quantities[row['ticker']] += float(row['quantity']) * (1 if row['type'] in ('BUY','ASSET_IN') else -1)
        return cash, quantities

    def valuation(day):
        if unsupported:
            return None, ['Odrębny model wyceny kont']
        cash, quantities = state(day, include_special=False)
        missing = [t for t, q in quantities.items() if abs(q) > .0001 and (q < 0 or not currencies.get(t))]
        value, no_prices = History._holding_value(quantities, {t: str(c).upper() for t, c in currencies.items()}, lambda t, d: History._price_at(index, t, d), day)
        missing = sorted(set(missing + no_prices))
        extra = [model['value'](day) for model in models]
        if any(v is None for v in extra):
            missing.append('PPK lub obligacje: brak danych wyceny')
        return (None if missing else cash + value + sum(extra)), missing

    opening, missing_open = valuation(start - timedelta(days=1))
    closing, missing_end = valuation(end)
    modeled_interest = 0.0
    reconciliation = {'cash_difference': None, 'positions_mismatch': [], 'consistent': None}
    if end == date.today() and not unsupported:
        buckets, messages = [], []
        for p in selected:
            if p in special_ids:
                continue
            own, issues = _own_snapshot(portfolios[p])
            buckets.extend(own.values()); messages.extend(issues)
            if portfolios[p]['account_type'] == 'SAVINGS':
                modeled_interest += own['savings'] - float(portfolios[p]['current_cash'] or 0)
        special_values = [model["value"](end) for model in models]
        closing = None if messages or any(v is None for v in special_values) else sum(buckets) + sum(special_values)
        warnings.extend(messages)
        ledger_cash, all_quantities = state(end)
        _,quantities=state(end,include_special=False)
        actual_cash = sum(float(portfolios[p]['current_cash'] or 0) for p in selected)
        # Modeled, not booked, savings interest is included in closing value only.
        difference = actual_cash - ledger_cash
        stored = defaultdict(float)
        for row in db.execute('SELECT portfolio_id,sub_portfolio_id,ticker,quantity FROM holdings'):
            if (row['sub_portfolio_id'] or row['portfolio_id']) in selected-special_ids:
                stored[row['ticker']] += float(row['quantity'])
        # Bond custody is separate from stock holdings; still reconcile its units.
        for model in models:
            for ticker,quantity in model['positions'](end).items():
                stored[ticker]+=quantity
                quantities[ticker]=all_quantities[ticker]
        for ticker,quantity in all_quantities.items():
            if ticker.startswith('BOND:'):
                quantities[ticker]=quantity
        mismatches = sorted(t for t in set(quantities) | set(stored) if abs(quantities[t] - stored[t]) > .0001)
        reconciliation = {'cash_difference': round(difference, 2), 'positions_mismatch': mismatches, 'consistent': abs(difference) <= .01 and not mismatches}
        if not reconciliation['consistent']:
            warnings.append('Aktualne saldo lub liczba jednostek nie zgadzają się z historią operacji. Stopy zwrotu są wstrzymane do wyjaśnienia różnicy.')
    if missing_open or missing_end:
        warnings.append('Brak pełnej wyceny granic okresu: ' + ', '.join(sorted(set(missing_open + missing_end))) + '.')
    stale = []
    _, terminal_quantities = state(end,include_special=False)
    held = {ticker for ticker, quantity in terminal_quantities.items() if quantity > .0001}
    terminal_prices = held | {f'{str(currencies[t]).upper()}PLN=X' for t in held if currencies.get(t) and str(currencies[t]).upper() != 'PLN'}
    for ticker in terminal_prices:
        # Age of the history price; a current cached quote may be newer.
        latest = max(prices[ticker], default=None)
        if latest and (end - date.fromisoformat(latest)).days > 7:
            stale.append(ticker)
    special_warnings = [w for model in models for day in (start-timedelta(days=1),end) for w in model['warnings_for'](day)]
    warnings.extend(special_warnings)
    if special_warnings:
        stale.append('PPK / obligacje')
    if stale:
        warnings.append('Historia cen jest starsza niż 7 dni dla: ' + ', '.join(sorted(stale)) + '. Wyniki historyczne mogą być nieaktualne.')
    reliable = not unsupported and reconciliation['consistent'] is not False
    profit = None if opening is None or closing is None else closing - opening - deposits + withdrawals
    dietz = modified_dietz(opening, closing, period_flows, start, end) if reliable and not stale else None
    investor_flows = ([(start - timedelta(days=1), -opening)] if opening else []) + [(day, -amount) for day, amount in period_flows]
    if closing is not None:
        investor_flows.append((end, closing))
    annual = money_weighted(investor_flows) if reliable and closing is not None and opening is not None and not stale else None
    months = []
    cursor = start
    while cursor <= end:
        following = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        last = min(following - timedelta(days=1), end)
        begin_value, missing_before = valuation(cursor - timedelta(days=1))
        final_value, missing_after = valuation(last)
        if last == end:
            final_value = closing
        month_issues=[w for model in models for day in (cursor-timedelta(days=1),last) for w in model['warnings_for'](day)]
        warnings.extend(month_issues)
        month_flows = [(day, amount) for day, amount in flows if cursor <= day <= last]
        net = sum(amount for _, amount in month_flows)
        result = None if begin_value is None or final_value is None else final_value - begin_value - net
        months.append({'date': last.isoformat(), 'opening_value': begin_value, 'closing_value': final_value,
                       'net_deposits': round(net, 2), 'profit': None if result is None else round(result, 2),
                       'return_percent': modified_dietz(begin_value, final_value, month_flows, cursor, last) if reliable and not stale and not month_issues else None,
                       'partial_month': cursor.day != 1 or last != following - timedelta(days=1),
                       'complete': not missing_before and not missing_after and final_value is not None and not month_issues})
        cursor = following
    def total(kind, field='total_value'):
        return round(sum(float(row[field] or 0) for row in active if row['type'] == kind), 2)
    positive = sum(1 for month in months if month['return_percent'] is not None and month['return_percent'] > 0)
    comparable = [m for m in months if m['return_percent'] is not None and not m['partial_month']]
    best = max(comparable, key=lambda m: m['return_percent']) if comparable else None
    worst = min(comparable, key=lambda m: m['return_percent']) if comparable else None
    if any(not month['complete'] for month in months) and not unsupported:
        warnings.append('Część miesięcy nie ma pełnej wyceny. Niepełne miesiące nie uczestniczą w porównaniu wyników.')
    return {'from': start.isoformat(), 'to': end.isoformat(), 'currency': 'PLN',
            'portfolio_names': [portfolios[p]['name'] for p in sorted(selected)],
            'status': 'unsupported' if unsupported else 'inconsistent' if not reliable else 'partial' if warnings else 'ok',
            'opening_value': None if opening is None else round(opening, 2), 'closing_value': None if closing is None else round(closing, 2),
            'deposits': round(deposits, 2), 'withdrawals': round(withdrawals, 2), 'net_deposits': round(deposits - withdrawals, 2),
            'profit': None if profit is None else round(profit, 2), 'dietz_percent': dietz, 'xirr_percent': annual,
            'dividends': total('DIVIDEND'), 'interest': total('INTEREST'), 'realized_profit': total('SELL', 'realized_profit'),
            'modeled_interest': round(modeled_interest, 2),
            'recorded_commissions': round(sum(float(r['commission'] or 0) for r in active if r['type'] in ('BUY', 'SELL')), 2),
            'transaction_count': len(active), 'internal_transfer_amount': round(sum(float(r['total_value']) for r in active if r['id'] in internal and r['type'] == 'DEPOSIT'), 2),
            'reconciliation': reconciliation, 'months': months, 'positive_months': positive,
            'known_months': sum(m['return_percent'] is not None for m in months),
            'best_month': best, 'worst_month': worst, 'warnings': list(dict.fromkeys(warnings)),
            'valuation_basis': 'PPK: jednostki brutto; obligacje: szacowana wartość netto; akcje i oszczędności: wycena z gotówką. Potrącenia przy zwrocie PPK nie są wynikiem funduszu.',
            'method': 'modified_dietz_end_of_day', 'annualization_min_days': 365}

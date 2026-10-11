"""Planning records and cached, read-only valuations. Never book transactions."""
import json
import math
from datetime import date, datetime, timezone

from valuation_quality import quote_status
from api.exceptions import NotFoundError, ValidationError
from database import get_db
from bond_service import BondService
from modules.ppk.ppk_service import PPKService
from portfolio_trade_service import PortfolioTradeService

ASSET_CLASSES = ('stocks', 'bonds', 'ppk', 'savings', 'cash')


def _number(value, label, minimum=0, maximum=1_000_000_000_000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValidationError(f'{label}: podaj liczbę od {minimum} do {maximum}.')
    return round(value, 2)


def _portfolios():
    return {row['id']: dict(row) for row in get_db().execute('SELECT * FROM portfolios')}


def _scope(portfolio_id, portfolios, visited=None):
    visited = set() if visited is None else set(visited)
    if portfolio_id in visited:
        raise ValidationError('Nieprawidłowa hierarchia portfeli.')
    visited.add(portfolio_id)
    p = portfolios.get(portfolio_id)
    if not p or p['is_archived']:
        return set()
    scope = {portfolio_id}
    for child in portfolios.values():
        if child['parent_portfolio_id'] == portfolio_id and not child['is_archived']:
            scope.update(_scope(child['id'], portfolios, visited))
    return scope


def _available(p, portfolios):
    visited = set()
    while p:
        if p['is_archived'] or p['id'] in visited:
            return False
        visited.add(p['id'])
        parent = p['parent_portfolio_id']
        if not parent:
            return True
        p = portfolios.get(parent)
    return False


def validate(data):
    if not isinstance(data, dict):
        raise ValidationError('Nieprawidłowe dane celu.')
    name = data.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValidationError('Nazwa celu musi mieć od 1 do 100 znaków.')
    description = data.get('description', '')
    if not isinstance(description, str) or len(description) > 1000:
        raise ValidationError('Opis może mieć najwyżej 1000 znaków.')
    target = _number(data.get('target_amount'), 'Kwota celu', .01)
    monthly = _number(data.get('monthly_contribution'), 'Miesięczna wpłata', 0, 1_000_000_000)
    annual = _number(data.get('annual_return'), 'Roczny zwrot', -50, 50)
    try:
        deadline = date.fromisoformat(data.get('target_date', ''))
        if deadline.isoformat() != data['target_date'] or not date(2000, 1, 1) <= deadline <= date(date.today().year + 60, 12, 31):
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise ValidationError('Podaj poprawny termin celu, nie dalej niż 60 lat.')
    ids = data.get('portfolio_ids')
    if not isinstance(ids, list) or not ids or any(type(value) is not int or value <= 0 for value in ids) or len(set(ids)) != len(ids):
        raise ValidationError('Wybierz co najmniej jeden portfel, bez powtórzeń.')
    portfolios = _portfolios()
    seen = set()
    for portfolio_id in ids:
        if portfolio_id not in portfolios or not _available(portfolios[portfolio_id], portfolios):
            raise ValidationError('Wybrany portfel nie istnieje albo został zarchiwizowany.')
        scope = _scope(portfolio_id, portfolios)
        if seen & scope:
            raise ValidationError('Wybierz portfel główny albo jego podportfele. Nie licz tych samych środków dwa razy.')
        seen.update(scope)
    allocation = data.get('target_allocation')
    if allocation is not None:
        if not isinstance(allocation, dict) or set(allocation) != set(ASSET_CLASSES):
            raise ValidationError('Uzupełnij udziały wszystkich kategorii struktury.')
        allocation = {key: _number(allocation[key], 'Udział kategorii', 0, 100) for key in ASSET_CLASSES}
        if abs(sum(allocation.values()) - 100) > .001:
            raise ValidationError('Docelowe udziały muszą sumować się do 100%.')
    return dict(name=name.strip(), description=description.strip(), target_amount=target, target_date=deadline.isoformat(),
                monthly_contribution=monthly, annual_return=annual, target_allocation=allocation, portfolio_ids=ids)


def save_goal(data, goal_id=None):
    db = get_db()
    if goal_id is not None and not db.execute('SELECT id FROM investment_goals WHERE id=?', (goal_id,)).fetchone():
        raise NotFoundError('Cel nie istnieje.')
    item = validate(data)
    now = datetime.now(timezone.utc).isoformat()
    fields = (item['name'], item['description'], item['target_amount'], item['target_date'], item['monthly_contribution'],
              item['annual_return'], json.dumps(item['target_allocation']) if item['target_allocation'] is not None else None, now)
    try:
        if goal_id is None:
            goal_id = db.execute('''INSERT INTO investment_goals
                (name,description,target_amount,target_date,monthly_contribution,annual_return,target_allocation,updated_at,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)''', (*fields, now)).lastrowid
        else:
            db.execute('''UPDATE investment_goals SET name=?,description=?,target_amount=?,target_date=?,
                monthly_contribution=?,annual_return=?,target_allocation=?,updated_at=? WHERE id=?''', (*fields, goal_id))
            db.execute('DELETE FROM investment_goal_portfolios WHERE goal_id=?', (goal_id,))
        db.executemany('INSERT INTO investment_goal_portfolios(goal_id,portfolio_id) VALUES (?,?)', [(goal_id, p) for p in item['portfolio_ids']])
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'id': goal_id}


def archive_goal(goal_id, archived):
    if type(archived) is not bool:
        raise ValidationError('Stan archiwizacji musi być wartością logiczną.')
    db = get_db()
    if not db.execute('SELECT id FROM investment_goals WHERE id=?', (goal_id,)).fetchone():
        raise NotFoundError('Cel nie istnieje.')
    try:
        db.execute('UPDATE investment_goals SET is_archived=?,updated_at=? WHERE id=?',
                   (int(archived), datetime.now(timezone.utc).isoformat(), goal_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'id': goal_id, 'is_archived': archived}


def _cached_quote(ticker):
    db = get_db()
    candidates = []
    for table, timestamp in (('price_cache', 'updated_at'), ('quotes_cache', 'updated_at'), ('stock_prices', 'date')):
        price = 'close_price' if table == 'stock_prices' else 'price'
        rows = db.execute(f'SELECT {price} AS price,{timestamp} AS updated FROM {table} WHERE ticker=? ORDER BY {timestamp} DESC LIMIT 1', (ticker,)).fetchall()
        for row in rows:
            if row['price'] is not None and math.isfinite(float(row['price'])) and float(row['price']) > 0:
                stamp = str(row['updated'] or '').replace(' ', 'T')
                # A history point has day precision; an intraday cache can supersede it.
                if stamp[:10] <= date.today().isoformat():
                    candidates.append((stamp, float(row['price'])))
    return max(candidates) if candidates else (None, None)


def _cached_price(ticker):
    return _cached_quote(ticker)[1]


def _own_snapshot(p):
    db = get_db()
    buckets = dict.fromkeys(ASSET_CLASSES, 0.0)
    warnings = []
    cash = float(p['current_cash'] or 0)
    kind = p['account_type']
    if kind == 'SAVINGS':
        interest = 0
        if p['last_interest_date']:
            days = max((date.today() - date.fromisoformat(str(p['last_interest_date']))).days, 0)
            interest = cash * float(p['savings_rate'] or 0) / 100 * days / 365
        buckets['savings'] = cash + interest
    elif kind == 'BONDS':
        buckets['cash'] = cash
        buckets['bonds'] = sum(b['total_value'] for b in BondService.get_bonds(p['id']))
    elif kind == 'PPK':
        buckets['cash'] = cash
        cached = PPKService.get_cached_price()
        if cached and float(cached['price']) > 0:
            buckets['ppk'] = float(PPKService.get_portfolio_summary(p['id'], cached['price'])['totalNetValue'])
            if quote_status(cached['price'], cached.get('date')) != 'ok':
                warnings.append(f"{p['name']}: nieaktualna cena PPK z {cached.get('date', 'brak daty')}; prognoza celu jest wstrzymana.")
        elif db.execute('SELECT 1 FROM ppk_transactions WHERE portfolio_id=? LIMIT 1', (p['id'],)).fetchone():
            warnings.append(f"{p['name']}: brak zapisanej ceny jednostki PPK.")
    else:
        buckets['cash'] = cash
        parent = p['parent_portfolio_id']
        holdings = db.execute('''SELECT h.ticker,h.quantity,COALESCE(h.currency,m.currency) AS currency
            FROM holdings h LEFT JOIN asset_metadata m ON m.ticker=h.ticker WHERE h.portfolio_id=?
            AND (h.sub_portfolio_id=? OR (h.sub_portfolio_id IS NULL AND ? IS NULL)) AND h.quantity>0.000001''',
            (parent or p['id'], p['id'] if parent else None, p['id'] if parent else None)).fetchall()
        for holding in holdings:
            stamp, price = _cached_quote(holding['ticker'])
            currency = str(holding['currency'] or '').upper()
            fx = 1 if currency == 'PLN' else _cached_price(f'{currency}PLN=X') if currency else None
            if price is None or fx is None:
                warnings.append(f"{holding['ticker']}: brak zapisanej ceny lub kursu waluty.")
                continue
            if quote_status(price, stamp) != 'ok':
                warnings.append(f"{holding['ticker']}: nieaktualna cena z {stamp or 'brak daty'}; prognoza celu jest wstrzymana.")
            if currency != 'PLN':
                fx_stamp, _ = _cached_quote(f'{currency}PLN=X')
                if quote_status(fx, fx_stamp) != 'ok':
                    warnings.append(f"{holding['ticker']}: nieaktualny kurs {currency}/PLN z {fx_stamp or 'brak daty'}.")
            gross = float(holding['quantity']) * price * fx
            buckets['stocks'] += gross - PortfolioTradeService._calculate_fx_fee(gross, currency)
    return buckets, warnings


def workspace():
    db = get_db()
    portfolios = _portfolios()
    cache = {}

    def snapshot(portfolio_id):
        if portfolio_id not in cache:
            buckets = dict.fromkeys(ASSET_CLASSES, 0.0)
            warnings = []
            scope = _scope(portfolio_id, portfolios)
            for own_id in scope:
                own_key = ('own', own_id)
                if own_key not in cache:
                    cache[own_key] = _own_snapshot(portfolios[own_id])
                own, messages = cache[own_key]
                for key in ASSET_CLASSES:
                    buckets[key] += own[key]
                warnings.extend(messages)
            cache[portfolio_id] = (buckets, warnings)
        return cache[portfolio_id]

    options = []
    for p in portfolios.values():
        if not _available(p, portfolios):
            continue
        buckets, warnings = snapshot(p['id'])
        options.append({'id': p['id'], 'name': p['name'], 'account_type': p['account_type'], 'parent_portfolio_id': p['parent_portfolio_id'],
                        'value': None if warnings else round(sum(buckets.values()), 2), 'warnings': warnings})
    goals = []
    scopes = {}
    for row in db.execute('SELECT * FROM investment_goals ORDER BY is_archived,id DESC'):
        goal = dict(row)
        goal['is_archived'] = bool(goal['is_archived'])
        goal['target_allocation'] = json.loads(goal['target_allocation']) if goal['target_allocation'] else None
        ids = [link['portfolio_id'] for link in db.execute('SELECT portfolio_id FROM investment_goal_portfolios WHERE goal_id=? ORDER BY portfolio_id', (goal['id'],))]
        goal['portfolio_ids'] = ids
        goal['portfolio_names'] = []
        buckets = dict.fromkeys(ASSET_CLASSES, 0.0)
        warnings = []
        seen = set()
        for portfolio_id in ids:
            p = portfolios.get(portfolio_id)
            goal['portfolio_names'].append(p['name'] if p else f'Usunięty portfel #{portfolio_id}')
            if not p or not _available(p, portfolios):
                warnings.append('Przypisany portfel został usunięty albo zarchiwizowany. Zmień przypisanie celu.')
                continue
            scope = _scope(portfolio_id, portfolios)
            if seen & scope:
                warnings.append('Portfele mają wspólne środki. Zmień przypisanie celu.')
                continue
            seen.update(scope)
            values, messages = snapshot(portfolio_id)
            for key in ASSET_CLASSES:
                buckets[key] += values[key]
            warnings.extend(messages)
        if not ids:
            warnings.append('Cel nie ma przypisanego portfela.')
        goal.update(current_value=None if warnings else round(sum(buckets.values()), 2),
                    allocation={key: round(value, 2) for key, value in buckets.items()}, warnings=list(dict.fromkeys(warnings)), overlapping_goals=[])
        scopes[goal['id']] = seen
        goals.append(goal)
    for goal in goals:
        if not goal['is_archived']:
            goal['overlapping_goals'] = [other['name'] for other in goals if other['id'] != goal['id'] and not other['is_archived'] and scopes[goal['id']] & scopes[other['id']]]
    return {'goals': goals, 'portfolios': options, 'as_of': date.today().isoformat()}

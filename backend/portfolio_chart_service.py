"""Read-only attribution of PLN results, including positions closed in the period."""
from collections import defaultdict
from datetime import date, timedelta

from api.exceptions import NotFoundError, ValidationError
from database import get_db
from portfolio_history_service import PortfolioHistoryService as History
from portfolio_valuation_service import PortfolioValuationService


def attribution(portfolio_id, start, end):
    if start > end or end > date.today():
        raise ValidationError('Invalid analysis dates')
    db = get_db()
    portfolio = db.execute('SELECT * FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
    if not portfolio:
        raise NotFoundError('Portfolio not found')
    if portfolio['account_type'] not in ('STANDARD', 'IKE', 'IKZE'):
        return {'items': [], 'status': 'unsupported_account', 'from': start.isoformat(), 'to': end.isoformat()}
    if portfolio['parent_portfolio_id']:
        scope, params = 'portfolio_id = ? AND sub_portfolio_id = ?', (portfolio['parent_portfolio_id'], portfolio_id)
    else:
        scope, params = History._sql_parent_scope_transactions(), (portfolio_id, portfolio_id)
    rows = db.execute(f'SELECT * FROM transactions WHERE {scope} AND date(date) <= ? ORDER BY date(date), id',
                      (*params, end.isoformat())).fetchall()
    tickers = {row['ticker'] for row in rows if row['ticker'] and row['ticker'] != 'CASH'}
    currencies, prices = History._build_price_context(portfolio_id, tickers, start - timedelta(days=1), portfolio['account_type'])
    price_index = History._build_sorted_price_index(prices)
    getter = lambda ticker, day: History._price_at(price_index, ticker, day)
    opening, closing, flows = defaultdict(float), defaultdict(float), defaultdict(float)
    dividends = defaultdict(float)
    for row in rows:
        ticker = row['ticker']
        if ticker not in tickers:
            continue
        before = History._to_date(row['date']) < start
        quantity = float(row['quantity'] or 0)
        if row['type'] in ('BUY', 'SELL'):
            change = quantity if row['type'] == 'BUY' else -quantity
            closing[ticker] += change
            if before:
                opening[ticker] += change
            else:
                flows[ticker] += PortfolioValuationService.cash_delta(row)
        elif not before and row['type'] == 'DIVIDEND':
            dividends[ticker] += float(row['total_value'] or 0)
    items, missing = [], []
    for ticker in sorted(tickers):
        start_value, missing_start = History._holding_value({ticker: opening[ticker]}, currencies, getter, start - timedelta(days=1))
        end_value, missing_end = History._holding_value({ticker: closing[ticker]}, currencies, getter, end)
        if missing_start or missing_end:
            missing.append(ticker)
            continue
        result = end_value - start_value + flows[ticker] + dividends[ticker]
        if abs(result) > .005 or opening[ticker] > 0 or closing[ticker] > 0 or flows[ticker] or dividends[ticker]:
            items.append({'ticker': ticker, 'value': round(result, 2), 'dividends': round(dividends[ticker], 2),
                          'opening_value': round(start_value, 2), 'closing_value': round(end_value, 2)})
    items.sort(key=lambda item: abs(item['value']), reverse=True)
    return {'items': items, 'missing_tickers': missing, 'status': 'partial' if missing else 'ok',
            'from': start.isoformat(), 'to': end.isoformat(), 'currency': 'PLN',
            'method': 'end_value_minus_opening_value_plus_trade_cash_and_dividends'}

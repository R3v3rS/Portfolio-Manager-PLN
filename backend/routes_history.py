from collections import defaultdict
from datetime import datetime, timezone

from flask import request

from api.response import success_response
from database import get_db
from portfolio_service import PortfolioService
from price_service import PriceService
from routes_portfolio_base import portfolio_bp


@portfolio_bp.route('/history/monthly/<int:portfolio_id>', methods=['GET'])
def get_portfolio_history_monthly(portfolio_id):
    benchmark = request.args.get('benchmark')
    if benchmark == '':
        benchmark = None

    history = PortfolioService.get_portfolio_history(portfolio_id, benchmark_ticker=benchmark)
    return success_response({'history': history})


@portfolio_bp.route('/history/profit/<int:portfolio_id>', methods=['GET'])
def get_portfolio_profit_history(portfolio_id):
    days = request.args.get('days', type=int)
    if days:
        history = PortfolioService.get_portfolio_profit_history_daily(portfolio_id, days=days)
    else:
        history = PortfolioService.get_portfolio_profit_history(portfolio_id)
    return success_response({'history': history})


@portfolio_bp.route('/history/value/<int:portfolio_id>', methods=['GET'])
def get_portfolio_value_history(portfolio_id):
    days = request.args.get('days', type=int)
    if days:
        history = PortfolioService.get_portfolio_value_history_daily(portfolio_id, days=days)
    else:
        history = PortfolioService.get_portfolio_history(portfolio_id)
    return success_response({'history': history})


@portfolio_bp.route('/history/<string:ticker>', methods=['GET'])
def get_stock_history(ticker):
    db = get_db()
    PriceService.sync_stock_history(ticker)

    prices = db.execute(
        'SELECT date, close_price FROM stock_prices WHERE ticker = ? ORDER BY date ASC',
        (ticker,)
    ).fetchall()
    last_updated = db.execute(
        'SELECT MAX(date) as last_date FROM stock_prices WHERE ticker = ?',
        (ticker,)
    ).fetchone()

    return success_response({
        'ticker': ticker,
        'history': [dict(price) for price in prices],
        'last_updated': last_updated['last_date'] if last_updated else None,
    })


@portfolio_bp.route('/<int:portfolio_id>/closed-positions', methods=['GET'])
def closed_positions(portfolio_id):
    db = get_db()
    rows = db.execute(
        '''SELECT t.ticker,
                  SUM(t.realized_profit) as realized_profit,
                  MAX(t.date) as last_sell_date,
                  COALESCE((
                      SELECT SUM(tb.total_value)
                      FROM transactions tb
                      WHERE tb.portfolio_id = t.portfolio_id
                        AND tb.ticker = t.ticker
                        AND tb.type = 'BUY'
                  ), 0) as invested_capital,
                  COALESCE(
                      MAX(NULLIF(h.company_name, '')),
                      MAX(NULLIF(m.company_name, ''))
                  ) as company_name
           FROM transactions t
           LEFT JOIN holdings h ON h.portfolio_id = t.portfolio_id AND h.ticker = t.ticker
           LEFT JOIN asset_metadata m ON m.ticker = t.ticker
           WHERE t.portfolio_id = ? AND t.type = 'SELL'
           GROUP BY t.ticker
           ORDER BY realized_profit DESC''',
        (portfolio_id,)
    ).fetchall()

    total = sum(row['realized_profit'] or 0 for row in rows)
    positions = [
        {
            'ticker': row['ticker'],
            'company_name': row['company_name'],
            'realized_profit': float(row['realized_profit'] or 0),
            'last_sell_date': str(row['last_sell_date']) if row['last_sell_date'] else None,
            'invested_capital': float(row['invested_capital'] or 0),
            'profit_percent_on_capital': (
                (float(row['realized_profit'] or 0) / float(row['invested_capital'])) * 100
                if (row['invested_capital'] or 0) > 0
                else None
            ),
        }
        for row in rows
    ]
    return success_response({'positions': positions, 'total_historical_profit': total})


@portfolio_bp.route('/<int:portfolio_id>/closed-position-cycles', methods=['GET'])
def closed_position_cycles(portfolio_id):
    db = get_db()
    tx_rows = db.execute(
        '''SELECT id, ticker, type, quantity, total_value, realized_profit, date
           FROM transactions
           WHERE portfolio_id = ?
             AND type IN ('BUY', 'SELL')''',
        (portfolio_id,)
    ).fetchall()

    def _parse_tx_date(value):
        if not value:
            return None
        str_value = str(value)
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(str_value, fmt)
            except ValueError:
                continue
        return None

    def _seconds_between(start, end):
        if not start or not end:
            return 0.0
        return max((end - start).total_seconds(), 0.0)

    def _annualized_return(realized_profit, average_capital, duration_seconds):
        if average_capital <= 1e-9 or duration_seconds <= 0:
            return None

        years = duration_seconds / (365.25 * 24 * 60 * 60)
        if years <= 0:
            return None

        return realized_profit / average_capital / years * 100

    tx_rows = sorted(tx_rows, key=lambda tx: (_parse_tx_date(tx['date']) or datetime.min, tx['id']))

    company_rows = db.execute(
        '''SELECT t.ticker as ticker,
                  COALESCE(
                      MAX(NULLIF(h.company_name, '')),
                      MAX(NULLIF(m.company_name, ''))
                  ) as company_name
           FROM transactions t
           LEFT JOIN holdings h ON h.portfolio_id = t.portfolio_id AND h.ticker = t.ticker
           LEFT JOIN asset_metadata m ON m.ticker = t.ticker
           WHERE t.portfolio_id = ?
           GROUP BY t.ticker''',
        (portfolio_id,)
    ).fetchall()

    company_names = {row['ticker']: row['company_name'] for row in company_rows}
    ticker_state = defaultdict(lambda: {
        'open_qty': 0.0,
        'cycle_id': 0,
        'opened_at': None,
        'invested_capital': 0.0,
        'cost_basis_open': 0.0,
        'realized_profit': 0.0,
        'buy_count': 0,
        'sell_count': 0,
        'capital_time_sum': 0.0,
        'last_event_at': None,
    })
    closed_cycles = []

    for tx in tx_rows:
        ticker = tx['ticker']
        tx_type = tx['type']
        quantity = float(tx['quantity'] or 0)
        tx_date_raw = tx['date']
        tx_dt = _parse_tx_date(tx_date_raw)
        state = ticker_state[ticker]

        if state['last_event_at'] and tx_dt:
            state['capital_time_sum'] += state['cost_basis_open'] * _seconds_between(state['last_event_at'], tx_dt)

        if tx_type == 'BUY':
            if state['open_qty'] <= 1e-9:
                state['cycle_id'] += 1
                state['opened_at'] = tx_date_raw
                state['invested_capital'] = 0.0
                state['cost_basis_open'] = 0.0
                state['realized_profit'] = 0.0
                state['buy_count'] = 0
                state['sell_count'] = 0
                state['capital_time_sum'] = 0.0

            state['open_qty'] += quantity
            buy_value = float(tx['total_value'] or 0)
            state['invested_capital'] += buy_value
            state['cost_basis_open'] += buy_value
            state['buy_count'] += 1
            state['last_event_at'] = tx_dt
            continue

        if tx_type == 'SELL':
            if state['open_qty'] <= 1e-9:
                state['last_event_at'] = tx_dt
                continue

            previous_qty = state['open_qty']
            if previous_qty > 1e-9:
                average_cost_per_share = state['cost_basis_open'] / previous_qty if state['cost_basis_open'] > 0 else 0.0
                state['cost_basis_open'] = max(0.0, state['cost_basis_open'] - average_cost_per_share * quantity)

            state['open_qty'] = max(0.0, state['open_qty'] - quantity)
            state['realized_profit'] += float(tx['realized_profit'] or 0)
            state['sell_count'] += 1
            state['last_event_at'] = tx_dt

            if state['open_qty'] <= 1e-9:
                realized_profit = float(state['realized_profit'])
                closed_dt = tx_dt
                opened_dt = _parse_tx_date(state['opened_at'])
                duration_seconds = _seconds_between(opened_dt, closed_dt)
                average_capital = (state['capital_time_sum'] / duration_seconds) if duration_seconds > 0 else None
                closed_cycles.append({
                    'ticker': ticker,
                    'company_name': company_names.get(ticker),
                    'cycle_id': int(state['cycle_id']),
                    'opened_at': str(state['opened_at']) if state['opened_at'] else None,
                    'closed_at': str(tx_date_raw) if tx_date_raw else None,
                    'invested_capital': float(state['invested_capital']),
                    'average_invested_capital': average_capital,
                    'holding_period_days': duration_seconds / (24 * 60 * 60) if duration_seconds > 0 else None,
                    'realized_profit': realized_profit,
                    'profit_percent_on_capital': (realized_profit / state['invested_capital'] * 100) if state['invested_capital'] > 0 else None,
                    'annualized_return_percent': _annualized_return(realized_profit, average_capital or 0.0, duration_seconds),
                    'buy_count': int(state['buy_count']),
                    'sell_count': int(state['sell_count']),
                    'status': 'CLOSED',
                    'is_partially_closed': False,
                    'remaining_quantity': 0.0,
                })
                state['open_qty'] = 0.0
                state['invested_capital'] = 0.0
                state['cost_basis_open'] = 0.0
                state['capital_time_sum'] = 0.0
                state['last_event_at'] = tx_dt

    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    for ticker, state in ticker_state.items():
        if state['open_qty'] > 1e-9 and state['sell_count'] > 0:
            invested_capital = float(state['invested_capital'])
            realized_profit = float(state['realized_profit'])
            effective_end_dt = state['last_event_at'] or now_dt
            capital_time_sum = state['capital_time_sum']
            if state['last_event_at']:
                capital_time_sum += state['cost_basis_open'] * _seconds_between(state['last_event_at'], now_dt)
                effective_end_dt = now_dt

            opened_dt = _parse_tx_date(state['opened_at'])
            duration_seconds = _seconds_between(opened_dt, effective_end_dt)
            average_capital = (capital_time_sum / duration_seconds) if duration_seconds > 0 else None

            closed_cycles.append({
                'ticker': ticker,
                'company_name': company_names.get(ticker),
                'cycle_id': int(state['cycle_id']),
                'opened_at': str(state['opened_at']) if state['opened_at'] else None,
                'closed_at': None,
                'invested_capital': invested_capital,
                'average_invested_capital': average_capital,
                'holding_period_days': duration_seconds / (24 * 60 * 60) if duration_seconds > 0 else None,
                'realized_profit': realized_profit,
                'profit_percent_on_capital': (realized_profit / invested_capital * 100) if invested_capital > 0 else None,
                'annualized_return_percent': _annualized_return(realized_profit, average_capital or 0.0, duration_seconds),
                'buy_count': int(state['buy_count']),
                'sell_count': int(state['sell_count']),
                'status': 'PARTIALLY_CLOSED',
                'is_partially_closed': True,
                'remaining_quantity': float(state['open_qty']),
            })

    closed_cycles.sort(
        key=lambda item: (
            1 if item.get('is_partially_closed') else 0,
            item['closed_at'] or '',
            item['ticker'],
            item['cycle_id'],
        ),
        reverse=True,
    )

    total = sum(item['realized_profit'] for item in closed_cycles)
    return success_response({'positions': closed_cycles, 'total_historical_profit': total})


@portfolio_bp.route('/<int:portfolio_id>/performance', methods=['GET'])
def get_performance_matrix(portfolio_id):
    matrix = PortfolioService.get_performance_matrix(portfolio_id)
    return success_response({'matrix': matrix})

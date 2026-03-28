from price_service import PriceService
from database import get_db
from datetime import datetime, timedelta, date
from portfolio_core_service import PortfolioCoreService
from portfolio_trade_service import PortfolioTradeService
from portfolio_valuation_service import PortfolioValuationService
from inflation_service import InflationService


class PortfolioHistoryService(PortfolioCoreService):
    _metrics_cache = {}

    @staticmethod
    def _build_price_context(portfolio_id, tickers, start_date, account_type, benchmark_ticker=None):
        db = get_db()
        ticker_currency: dict[str, str] = {}
        # Fetch current holdings to get currencies
        holding_rows = db.execute('SELECT DISTINCT ticker, currency FROM holdings WHERE portfolio_id = ? AND ticker IS NOT NULL', (portfolio_id,)).fetchall()
        for row in holding_rows:
            if row['ticker'] and row['ticker'] != 'CASH':
                ticker = row['ticker']
                currency = (row['currency'] or 'PLN').upper()
                # Double check with metadata if currency is PLN, as it might be an incorrect default
                if currency == 'PLN':
                    try:
                        meta = PriceService.fetch_metadata(ticker)
                        if meta and meta.get('currency') and meta['currency'].upper() != 'PLN':
                            currency = meta['currency'].upper()
                    except Exception:
                        pass
                ticker_currency[ticker] = currency

        # Ensure all tickers in transactions have a currency assigned
        for ticker in tickers:
            if ticker not in ticker_currency:
                try:
                    meta = PriceService.fetch_metadata(ticker)
                    ticker_currency[ticker] = ((meta or {}).get('currency') or 'PLN').upper()
                except Exception:
                    ticker_currency[ticker] = 'PLN'

        fx_tickers = {f"{currency}PLN=X" for currency in set(ticker_currency.values()) if currency != 'PLN'}
        sync_tickers = set(tickers)
        sync_tickers.update(fx_tickers)
        if benchmark_ticker and benchmark_ticker != '__INFLATION__':
            sync_tickers.add(benchmark_ticker)

        if account_type not in ['SAVINGS', 'BONDS'] or (benchmark_ticker and benchmark_ticker != '__INFLATION__'):
            tickers_to_sync = PriceService.get_tickers_requiring_history_sync(sync_tickers, start_date)
            for ticker in tickers_to_sync:
                try:
                    PriceService.sync_stock_history(ticker, start_date)
                except Exception as e:
                    print(f"Failed to sync history for {ticker}: {e}")

        price_history = {}
        if account_type not in ['SAVINGS', 'BONDS'] or (benchmark_ticker and benchmark_ticker != '__INFLATION__'):
            for ticker in sync_tickers:
                rows = db.execute('SELECT date, close_price FROM stock_prices WHERE ticker = ? ORDER BY date ASC', (ticker,)).fetchall()
                price_history[ticker] = {str(row['date']).split(' ')[0].split('T')[0]: row['close_price'] for row in rows}
        
        return ticker_currency, price_history

    @staticmethod
    def _calculate_historical_metrics(portfolio_id, benchmark_ticker=None):
        cache_key = (portfolio_id, benchmark_ticker)
        if cache_key in PortfolioHistoryService._metrics_cache:
            return PortfolioHistoryService._metrics_cache[cache_key]

        db = get_db()
        # Resolve portfolio and its parent/child status
        portfolio = db.execute('SELECT id, account_type, created_at, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            return {}
            
        account_type = portfolio['account_type']
        
        if portfolio['parent_portfolio_id']:
            # It's a child - filter transactions by parent_id and this child_id
            actual_portfolio_id = portfolio['parent_portfolio_id']
            actual_sub_portfolio_id = portfolio['id']
            tx_query = 'SELECT * FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id = ? ORDER BY date ASC'
            tx_params = (actual_portfolio_id, actual_sub_portfolio_id)
        else:
            # It's a parent - include all transactions for this portfolio (parent's own + all children)
            actual_portfolio_id = portfolio['id']
            tx_query = 'SELECT * FROM transactions WHERE portfolio_id = ? ORDER BY date ASC'
            tx_params = (actual_portfolio_id,)

        transactions = db.execute(tx_query, tx_params).fetchall()
        if not transactions:
            return {}

        first_trans_date = transactions[0]['date']
        if isinstance(first_trans_date, str):
            start_date = datetime.strptime(first_trans_date.split(' ')[0], '%Y-%m-%d').date()
        else:
            start_date = first_trans_date
        today = date.today()

        month_ends = []
        curr_y, curr_m = start_date.year, start_date.month
        while date(curr_y, curr_m, 1) <= today:
            if curr_m == 12:
                next_m, next_y = 1, curr_y + 1
            else:
                next_m, next_y = curr_m + 1, curr_y
            month_end = date(next_y, next_m, 1) - timedelta(days=1)
            if month_end > today:
                month_end = today
            month_ends.append(month_end)
            if month_end == today:
                break
            curr_m, curr_y = next_m, next_y

        tickers = {t['ticker'] for t in transactions if t['ticker'] not in ['CASH', '']}
        ticker_currency, price_history = PortfolioHistoryService._build_price_context(
            portfolio_id, tickers, start_date, account_type, benchmark_ticker
        )

        inflation_map = {}
        # Always fetch inflation data to support the "benchmark_inflation" field in history
        inf_series = InflationService.get_inflation_series(start_date.strftime('%Y-%m'), today.strftime('%Y-%m'))
        inflation_map = {item['date']: item['index_value'] for item in inf_series}

        def get_price_at_date(ticker, target_date):
            if ticker == '__INFLATION__':
                month_key = target_date.strftime('%Y-%m')
                if month_key in inflation_map:
                    return inflation_map[month_key]
                past_months = sorted([m for m in inflation_map.keys() if m <= month_key])
                if past_months:
                    return inflation_map[past_months[-1]]
                return 0

            if ticker not in price_history or not price_history[ticker]:
                return 0
            target_str = target_date.strftime('%Y-%m-%d')
            if target_str in price_history[ticker]:
                return price_history[ticker][target_str]
            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]
            if past_dates:
                return price_history[ticker][max(past_dates)]
            return 0

        monthly_data = {}
        for end_date in month_ends:
            current_cash = 0.0
            invested_capital = 0.0
            holdings_qty = {}
            benchmark_shares = 0.0
            inflation_shares = 0.0
            for t in transactions:
                t_date_str = str(t['date']).split(' ')[0].split('T')[0]
                t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                if t_date > end_date:
                    continue
                t_val = float(t['total_value'])
                t_qty = float(t['quantity'])
                t_ticker = t['ticker']
                if t['type'] in ['DEPOSIT', 'SELL', 'DIVIDEND', 'INTEREST']:
                    current_cash += t_val
                elif t['type'] in ['WITHDRAW', 'BUY']:
                    current_cash -= t_val
                if t['type'] == 'DEPOSIT':
                    invested_capital += t_val
                    if benchmark_ticker and benchmark_ticker != '__INFLATION__':
                        bp = get_price_at_date(benchmark_ticker, t_date)
                        if bp > 0:
                            benchmark_shares += (t_val / bp)
                    
                    ip = get_price_at_date('__INFLATION__', t_date)
                    if ip > 0:
                        inflation_shares += (t_val / ip)

                elif t['type'] == 'WITHDRAW':
                    invested_capital -= t_val
                    if benchmark_ticker and benchmark_ticker != '__INFLATION__':
                        bp = get_price_at_date(benchmark_ticker, t_date)
                        if bp > 0:
                            benchmark_shares -= (t_val / bp)
                    
                    ip = get_price_at_date('__INFLATION__', t_date)
                    if ip > 0:
                        inflation_shares -= (t_val / ip)
                
                if t_ticker != 'CASH':
                    if t['type'] == 'BUY':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) + t_qty
                    elif t['type'] == 'SELL':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) - t_qty

            holdings_value = 0.0
            if account_type not in ['SAVINGS', 'BONDS']:
                for ticker, qty in holdings_qty.items():
                    if qty > 0.0001:
                        native_price = get_price_at_date(ticker, end_date)
                        currency = ticker_currency.get(ticker, 'PLN')
                        fx_rate = 1.0 if currency == 'PLN' else get_price_at_date(f"{currency}PLN=X", end_date)
                        if fx_rate <= 0:
                            fx_rate = 1.0
                        gross_value_pln = qty * native_price * fx_rate
                        net_value_pln = gross_value_pln - PortfolioTradeService._calculate_fx_fee(gross_value_pln, currency)
                        holdings_value += net_value_pln

            total_value = current_cash + holdings_value
            profit = total_value - invested_capital

            # Keep the latest monthly point fully aligned with the live valuation endpoint.
            # This avoids overstating/understating "today" versus the current portfolio value.
            if end_date == today:
                live_value = PortfolioValuationService.get_portfolio_value(portfolio_id)
                if live_value:
                    total_value = float(live_value.get('portfolio_value', total_value))
                    current_cash = float(live_value.get('cash_value', current_cash))
                    holdings_value = float(live_value.get('holdings_value', holdings_value))
                    profit = total_value - invested_capital

            metrics = {
                "total_value": total_value,
                "profit": profit,
                "net_contributions": invested_capital,
                "cash_value": round(current_cash, 2),
                "holdings_value": round(holdings_value, 2),
            }
            if benchmark_ticker and benchmark_ticker != '__INFLATION__':
                bp_end = get_price_at_date(benchmark_ticker, end_date)
                metrics["benchmark_value"] = round(benchmark_shares * bp_end, 2)
            
            ip_end = get_price_at_date('__INFLATION__', end_date)
            metrics["benchmark_inflation_value"] = round(inflation_shares * ip_end, 2)
            
            monthly_data[end_date.strftime('%Y-%m')] = metrics
        
        PortfolioHistoryService._metrics_cache[cache_key] = monthly_data
        return monthly_data

    @staticmethod
    def get_portfolio_history(portfolio_id, benchmark_ticker=None):
        monthly_data = PortfolioHistoryService._calculate_historical_metrics(portfolio_id, benchmark_ticker)
        if not monthly_data:
            return []
            
        sorted_keys = sorted(monthly_data.keys())
        result = []
        for k in sorted_keys:
            dt = datetime.strptime(k, '%Y-%m')
            entry = {
                'date': k,
                'label': dt.strftime('%b %Y'),
                'value': round(monthly_data[k]['total_value'], 2),
                'net_contributions': round(monthly_data[k].get('net_contributions', 0.0), 2),
                'cash_value': round(monthly_data[k].get('cash_value', 0), 2),
                'holdings_value': round(monthly_data[k].get('holdings_value', 0), 2),
            }
            
            # If inflation is the primary benchmark, set it to benchmark_value
            if benchmark_ticker == '__INFLATION__':
                entry['benchmark_value'] = monthly_data[k].get('benchmark_inflation_value', 0.0)
            elif 'benchmark_value' in monthly_data[k]:
                entry['benchmark_value'] = monthly_data[k]['benchmark_value']
            
            # Always provide inflation adjusted contributions for the overlay checkbox
            if 'benchmark_inflation_value' in monthly_data[k]:
                entry['benchmark_inflation'] = monthly_data[k]['benchmark_inflation_value']
                
            result.append(entry)
        return result

    @staticmethod
    def get_portfolio_profit_history(portfolio_id):
        monthly_data = PortfolioHistoryService._calculate_historical_metrics(portfolio_id)
        if not monthly_data:
            return []
        result = []
        for k in sorted(monthly_data.keys()):
            dt = datetime.strptime(k, '%Y-%m')
            result.append({'date': k, 'label': dt.strftime('%b %Y'), 'value': round(monthly_data[k]['profit'], 2)})
        return result

    @staticmethod
    def get_portfolio_profit_history_daily(portfolio_id, days=30, metric="profit"):
        db = get_db()
        days = max(1, min(int(days), 365))
        
        # Resolve portfolio and its parent/child status
        portfolio = db.execute('SELECT id, account_type, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            return []
            
        account_type = portfolio['account_type']
        
        if portfolio['parent_portfolio_id']:
            # It's a child - filter transactions by parent_id and this child_id
            actual_portfolio_id = portfolio['parent_portfolio_id']
            actual_sub_portfolio_id = portfolio['id']
            tx_query = 'SELECT ticker, type, quantity, total_value, date FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id = ? ORDER BY date ASC'
            tx_params = (actual_portfolio_id, actual_sub_portfolio_id)
        else:
            # It's a parent - include all transactions for this portfolio (parent's own + all children)
            actual_portfolio_id = portfolio['id']
            tx_query = 'SELECT ticker, type, quantity, total_value, date FROM transactions WHERE portfolio_id = ? ORDER BY date ASC'
            tx_params = (actual_portfolio_id,)

        transactions = db.execute(tx_query, tx_params).fetchall()
        if not transactions:
            return []
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        date_points = [start_date + timedelta(days=offset) for offset in range(days)]
        tickers = {t['ticker'] for t in transactions if t['ticker'] not in ['CASH', '']}

        ticker_currency, price_history = PortfolioHistoryService._build_price_context(
            portfolio_id, tickers, start_date, account_type
        )

        def get_price_at_date(ticker, target_date):
            if ticker not in price_history or not price_history[ticker]:
                return 0
            target_str = target_date.strftime('%Y-%m-%d')
            if target_str in price_history[ticker]:
                return price_history[ticker][target_str]
            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]
            if past_dates:
                return price_history[ticker][max(past_dates)]
            return 0

        result = []
        for point_date in date_points:
            current_cash = 0.0
            invested_capital = 0.0
            holdings_qty = {}
            for t in transactions:
                t_date_str = str(t['date']).split(' ')[0].split('T')[0]
                t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                if t_date > point_date:
                    continue
                t_val = float(t['total_value'])
                t_qty = float(t['quantity'])
                t_ticker = t['ticker']
                if t['type'] in ['DEPOSIT', 'SELL', 'DIVIDEND', 'INTEREST']:
                    current_cash += t_val
                elif t['type'] in ['WITHDRAW', 'BUY']:
                    current_cash -= t_val
                if t['type'] == 'DEPOSIT':
                    invested_capital += t_val
                elif t['type'] == 'WITHDRAW':
                    invested_capital -= t_val
                if t_ticker != 'CASH':
                    if t['type'] == 'BUY':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) + t_qty
                    elif t['type'] == 'SELL':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) - t_qty

            total_value = current_cash
            if account_type not in ['SAVINGS', 'BONDS']:
                for ticker, qty in holdings_qty.items():
                    if qty > 0.0001:
                        native_price = get_price_at_date(ticker, point_date)
                        currency = ticker_currency.get(ticker, 'PLN')
                        fx_rate = 1.0 if currency == 'PLN' else get_price_at_date(f"{currency}PLN=X", point_date)
                        if fx_rate <= 0:
                            fx_rate = 1.0
                        gross_value_pln = qty * native_price * fx_rate
                        net_value_pln = gross_value_pln - PortfolioTradeService._calculate_fx_fee(gross_value_pln, currency)
                        total_value += net_value_pln

            if point_date == end_date:
                live_value = PortfolioValuationService.get_portfolio_value(portfolio_id)
                if live_value:
                    total_value = float(live_value.get('portfolio_value', total_value))
                    # Sync invested_capital from live_value if available
                    live_invested = live_value.get('invested_capital') or live_value.get('net_contributions')
                    if live_invested is not None:
                        invested_capital = float(live_invested)

            value = total_value if metric == 'value' else total_value - invested_capital
            result.append({'date': point_date.strftime('%Y-%m-%d'), 'label': point_date.strftime('%d %b'), 'value': round(value, 2)})
        return result

    @staticmethod
    def get_portfolio_value_history_daily(portfolio_id, days=30):
        return PortfolioHistoryService.get_portfolio_profit_history_daily(portfolio_id, days=days, metric='value')

    @staticmethod
    def get_performance_matrix(portfolio_id):
        monthly_values_map = PortfolioHistoryService._calculate_historical_metrics(portfolio_id)
        if not monthly_values_map:
            return {}
        db = get_db()
        
        # Resolve portfolio and its parent/child status
        portfolio = db.execute('SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            return {}

        if portfolio['parent_portfolio_id']:
            # It's a child - filter transactions by parent_id and this child_id
            actual_portfolio_id = portfolio['parent_portfolio_id']
            actual_sub_portfolio_id = portfolio['id']
            tx_query = "SELECT date, type, total_value FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id = ? AND type IN ('DEPOSIT', 'WITHDRAW') ORDER BY date ASC"
            tx_params = (actual_portfolio_id, actual_sub_portfolio_id)
        else:
            # It's a parent - include all transactions for this portfolio (parent's own + all children)
            actual_portfolio_id = portfolio['id']
            tx_query = "SELECT date, type, total_value FROM transactions WHERE portfolio_id = ? AND type IN ('DEPOSIT', 'WITHDRAW') ORDER BY date ASC"
            tx_params = (actual_portfolio_id,)

        transactions = db.execute(tx_query, tx_params).fetchall()
        monthly_flows = {}
        for t in transactions:
            t_date_str = str(t['date']).split(' ')[0]
            month_key = t_date_str[:7]
            amount = float(t['total_value'])
            monthly_flows.setdefault(month_key, 0.0)
            if t['type'] == 'DEPOSIT':
                monthly_flows[month_key] += amount
            elif t['type'] == 'WITHDRAW':
                monthly_flows[month_key] -= amount

        results = {}
        previous_end_value = 0.0
        yearly_compounding = {}
        for month_key in sorted(monthly_values_map.keys()):
            year, month = month_key.split('-')
            year_key = str(year)
            month_int = str(int(month))
            if year_key not in results:
                results[year_key] = {}
                yearly_compounding[year_key] = 1.0
            end_value = monthly_values_map[month_key]['total_value']
            net_flows = monthly_flows.get(month_key, 0.0)
            start_value = previous_end_value
            profit = end_value - start_value - net_flows
            denominator = start_value + (net_flows / 2.0)
            
            if denominator <= 0:
                monthly_return = None
                results[year_key][month_int] = None
            else:
                monthly_return = profit / denominator
                results[year_key][month_int] = round(monthly_return * 100, 2)
                yearly_compounding[year_key] *= (1.0 + monthly_return)
            
            results[year_key]['YTD'] = round((yearly_compounding[year_key] - 1.0) * 100, 2)
            previous_end_value = end_value
        return results

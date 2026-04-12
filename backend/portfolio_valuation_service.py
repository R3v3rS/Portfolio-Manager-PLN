from price_service import PriceService
from database import get_db
from datetime import datetime, date
from bond_service import BondService
from math_utils import xirr
from modules.ppk.ppk_service import PPKService
from portfolio_core_service import PortfolioCoreService
from portfolio_trade_service import PortfolioTradeService
from collections import defaultdict


class PortfolioValuationService(PortfolioCoreService):
    CONSISTENCY_TOLERANCE_PLN = 0.01

    @staticmethod
    def cash_delta(tx):
        tx_type = tx['type']
        amount = float(tx['total_value'] or 0.0)

        if tx_type in ('DEPOSIT', 'INTEREST', 'SELL', 'DIVIDEND'):
            return amount
        if tx_type in ('WITHDRAW', 'BUY'):
            return -amount
        if tx_type == 'TRANSFER':
            return 0.0
        return 0.0

    @staticmethod
    def _sum_cash_deltas(tx_rows):
        return sum(PortfolioValuationService.cash_delta(row) for row in tx_rows)

    @staticmethod
    def _compute_cash_negative_days(parent_id, scope_portfolio_id):
        db = get_db()
        is_child_scope = parent_id != scope_portfolio_id

        if is_child_scope:
            tx_rows = db.execute(
                '''
                SELECT id, date, type, total_value
                FROM transactions
                WHERE (portfolio_id = ? AND sub_portfolio_id = ?)
                   OR (portfolio_id = ? AND (sub_portfolio_id IS NULL OR sub_portfolio_id = 0))
                ORDER BY date(date) ASC, id ASC
                ''',
                (parent_id, scope_portfolio_id, scope_portfolio_id),
            ).fetchall()
        else:
            tx_rows = db.execute(
                '''
                SELECT id, date, type, total_value
                FROM transactions
                WHERE portfolio_id = ?
                  AND (sub_portfolio_id IS NULL OR sub_portfolio_id = 0)
                ORDER BY date(date) ASC, id ASC
                ''',
                (parent_id,),
            ).fetchall()

        if not tx_rows:
            return {'ok': True, 'incidents': []}

        grouped_by_date = {}
        first_tx_date = None
        for row in tx_rows:
            tx_date = str(row['date']).split(' ')[0]
            if first_tx_date is None:
                first_tx_date = tx_date
            grouped_by_date.setdefault(tx_date, []).append(row)

        incidents = []
        running_balance = 0.0
        carrying_trigger = None
        current_day = datetime.strptime(first_tx_date, '%Y-%m-%d').date()
        last_day = date.today()

        while current_day <= last_day:
            day_key = current_day.isoformat()
            day_rows = grouped_by_date.get(day_key, [])
            day_trigger = carrying_trigger

            for row in day_rows:
                amount = float(row['total_value'] or 0.0)
                prev_balance = running_balance
                running_balance += PortfolioValuationService.cash_delta(row)
                if prev_balance >= 0 and running_balance < 0:
                    day_trigger = {
                        'triggering_transaction_id': int(row['id']),
                        'triggering_type': row['type'],
                        'triggering_amount': round(amount, 2),
                    }

            if running_balance < 0:
                if day_trigger is None:
                    fallback_row = day_rows[-1] if day_rows else None
                    if fallback_row is not None:
                        day_trigger = {
                            'triggering_transaction_id': int(fallback_row['id']),
                            'triggering_type': fallback_row['type'],
                            'triggering_amount': round(float(fallback_row['total_value'] or 0.0), 2),
                        }
                    else:
                        day_trigger = {
                            'triggering_transaction_id': None,
                            'triggering_type': None,
                            'triggering_amount': 0.0,
                        }
                incidents.append({
                    'date': day_key,
                    'balance_pln': round(running_balance, 2),
                    **day_trigger,
                })
                carrying_trigger = day_trigger
            else:
                carrying_trigger = None

            current_day = current_day.fromordinal(current_day.toordinal() + 1)

        return {
            'ok': len(incidents) == 0,
            'incidents': incidents,
        }

    @staticmethod
    def get_cash_balance_on_date(portfolio_id, as_of_date, sub_portfolio_id=None):
        db = get_db()
        if sub_portfolio_id is None:
            portfolio = db.execute('SELECT parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()

            if portfolio and portfolio['parent_portfolio_id'] is None:
                tx_rows = db.execute(
                    '''
                    SELECT type, total_value
                    FROM transactions
                    WHERE portfolio_id = ?
                      AND date(date) <= date(?)
                    ''',
                    (portfolio_id, as_of_date),
                ).fetchall()
                return float(PortfolioValuationService._sum_cash_deltas(tx_rows))

            tx_rows = db.execute(
                '''
                SELECT type, total_value
                FROM transactions
                WHERE portfolio_id = ?
                  AND (sub_portfolio_id IS NULL OR sub_portfolio_id = 0)
                  AND date(date) <= date(?)
                ''',
                (portfolio_id, as_of_date),
            ).fetchall()
            return float(PortfolioValuationService._sum_cash_deltas(tx_rows))

        tx_rows = db.execute(
            '''
            SELECT type, total_value
            FROM transactions
            WHERE portfolio_id = ?
              AND sub_portfolio_id = ?
              AND date(date) <= date(?)
            ''',
            (portfolio_id, sub_portfolio_id, as_of_date),
        ).fetchall()
        legacy_rows = db.execute(
            '''
            SELECT type, total_value
            FROM transactions
            WHERE portfolio_id = ?
              AND (sub_portfolio_id IS NULL OR sub_portfolio_id = 0)
              AND date(date) <= date(?)
            ''',
            (sub_portfolio_id, as_of_date),
        ).fetchall()
        return float(
            PortfolioValuationService._sum_cash_deltas(tx_rows)
            + PortfolioValuationService._sum_cash_deltas(legacy_rows)
        )

    @staticmethod
    def calculate_metrics(holdings, total_value, cash_value):
        if total_value == 0:
            return []
        enriched = []
        for h in holdings:
            weight = (h.get('current_value', 0) / total_value) * 100
            h['weight_percent'] = round(weight, 2)
            enriched.append(h)
        return enriched

    @staticmethod
    def get_equity_allocation(portfolio_id):
        holdings = PortfolioValuationService.get_holdings(portfolio_id)
        if not holdings:
            return []
        
        # Calculate total value of equities (excluding cash/bonds which are not in 'holdings' table)
        total_equity_value = sum(float(h.get('current_value', 0.0) or 0.0) for h in holdings)
        
        if total_equity_value <= 0:
            return []
            
        allocation = []
        for h in holdings:
            val = float(h.get('current_value', 0.0) or 0.0)
            percentage = (val / total_equity_value) * 100
            allocation.append({
                'ticker': h['ticker'],
                'name': h.get('company_name') or h['ticker'],
                'value': round(val, 2),
                'percentage': round(percentage, 2)
            })
            
        # Sort by percentage descending
        allocation.sort(key=lambda x: x['percentage'], reverse=True)
        return allocation

    @staticmethod
    def _get_open_cycle_realized_profit_map(portfolio_id, sub_portfolio_id=None, aggregate=True):
        db = get_db()
        query = '''
            SELECT ticker, type, quantity, realized_profit, date, id, sub_portfolio_id
            FROM transactions
            WHERE portfolio_id = ?
              AND type IN ('BUY', 'SELL')
        '''
        params = [portfolio_id]

        if sub_portfolio_id is not None:
            query += ' AND sub_portfolio_id = ?'
            params.append(sub_portfolio_id)
        elif not aggregate:
            query += ' AND sub_portfolio_id IS NULL'

        query += ' ORDER BY date ASC, id ASC'
        tx_rows = db.execute(query, tuple(params)).fetchall()

        ticker_context_state = defaultdict(lambda: {'open_qty': 0.0, 'realized_profit': 0.0})
        for tx in tx_rows:
            ticker = tx['ticker']
            raw_sub = tx['sub_portfolio_id']
            normalized_sub = None if (raw_sub is None or raw_sub == 0) else raw_sub
            context_key = (ticker, normalized_sub)
            tx_type = tx['type']
            quantity = float(tx['quantity'] or 0.0)
            state = ticker_context_state[context_key]

            if tx_type == 'BUY':
                if state['open_qty'] <= 1e-9:
                    state['realized_profit'] = 0.0
                state['open_qty'] += quantity
                continue

            if tx_type == 'SELL':
                if state['open_qty'] <= 1e-9:
                    continue
                state['open_qty'] = max(0.0, state['open_qty'] - quantity)
                state['realized_profit'] += float(tx['realized_profit'] or 0.0)
                if state['open_qty'] <= 1e-9:
                    state['realized_profit'] = 0.0

        if not aggregate:
            return {
                ticker: float(state['realized_profit'])
                for (ticker, _), state in ticker_context_state.items()
                if state['open_qty'] > 1e-9
            }

        by_ticker = defaultdict(float)
        for (ticker, _), state in ticker_context_state.items():
            if state['open_qty'] > 1e-9:
                by_ticker[ticker] += float(state['realized_profit'])
        return dict(by_ticker)

    @staticmethod
    def _calculate_break_even_sell_price_pln(quantity, total_cost, realized_profit, currency):
        qty = float(quantity or 0.0)
        if qty <= 1e-9:
            return None
        target_net_proceeds = float(total_cost or 0.0) - float(realized_profit or 0.0)
        fee_multiplier = 1.0 - PortfolioTradeService.FX_FEE_RATE if (currency or 'PLN').upper() != 'PLN' else 1.0
        if fee_multiplier <= 1e-9:
            return None
        gross_proceeds = target_net_proceeds / fee_multiplier
        return max(0.0, gross_proceeds / qty)

    @staticmethod
    def get_holdings(portfolio_id, force_price_refresh=False, sub_portfolio_id=None, aggregate=True):
        db = get_db()
        
        # Check if the provided portfolio_id is actually a child
        portfolio = db.execute('SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            return []
            
        if portfolio['parent_portfolio_id']:
            # It's a child portfolio. We need to query by parent_id and this child_id.
            actual_portfolio_id = portfolio['parent_portfolio_id']
            actual_sub_portfolio_id = portfolio['id']
        else:
            # It's a parent portfolio.
            actual_portfolio_id = portfolio['id']
            actual_sub_portfolio_id = sub_portfolio_id # Might be None (parent's own) or specific child

        if actual_sub_portfolio_id is not None:
            holdings = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id = ?', 
                                 (actual_portfolio_id, actual_sub_portfolio_id)).fetchall()
        elif aggregate:
            # It's a parent portfolio and we want AGGREGATED view.
            # Aggregate holdings by ticker and currency.
            # Sum quantity and calculate weighted average buy price and total cost.
            holdings = db.execute('''
                SELECT 
                    ticker, 
                    currency,
                    company_name,
                    sector,
                    industry,
                    SUM(quantity) as quantity,
                    SUM(total_cost) as total_cost,
                    CASE WHEN SUM(quantity) > 0 THEN SUM(total_cost) / SUM(quantity) ELSE 0 END as average_buy_price,
                    MAX(id) as id -- Just for reference
                FROM holdings 
                WHERE portfolio_id = ? 
                GROUP BY ticker, currency
            ''', (actual_portfolio_id,)).fetchall()
        else:
            # It's a parent portfolio but we want ONLY its own holdings (where sub_portfolio_id IS NULL)
            holdings = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id IS NULL', 
                                 (actual_portfolio_id,)).fetchall()
            
        results = []
        if not holdings:
            return results

        tickers = [h['ticker'] for h in holdings]
        current_prices = PriceService.get_prices(tickers, force_refresh=force_price_refresh)
        price_updates = PriceService.get_price_updates(tickers)
        quotes = PriceService.get_quotes(tickers)
        fx_rates = PortfolioTradeService._get_fx_rates_to_pln({h['currency'] or 'PLN' for h in holdings})
        updates_needed = False
        holdings_value = 0.0
        open_cycle_realized_profit_by_ticker = PortfolioValuationService._get_open_cycle_realized_profit_map(
            actual_portfolio_id,
            sub_portfolio_id=actual_sub_portfolio_id,
            aggregate=aggregate,
        )

        for h in holdings:
            if h['quantity'] < 0.000001:
                continue
            h_dict = {key: h[key] for key in h.keys()}
            if not h_dict.get('company_name') or not h_dict.get('sector'):
                meta = PriceService.fetch_metadata(h_dict['ticker'])
                if meta:
                    db.execute('UPDATE holdings SET company_name = ?, sector = ?, industry = ? WHERE id = ?', (meta['company_name'], meta['sector'], meta['industry'], h_dict['id']))
                    h_dict.update(meta)
                    updates_needed = True

            price_native = current_prices.get(h_dict['ticker'])
            if price_native is None:
                currency = (h_dict.get('currency') or 'PLN').upper()
                fx_rate = fx_rates.get(currency, 1.0)
                price_native = (h_dict['average_buy_price'] / fx_rate) if fx_rate else h_dict['average_buy_price']

            currency = (h_dict.get('currency') or 'PLN').upper()
            fx_rate = fx_rates.get(currency, 1.0)
            price_pln = price_native * fx_rate
            h_dict['current_price'] = price_native
            quote = quotes.get(h_dict['ticker'], {})
            prev_close = quote.get('prev_close')
            if prev_close not in (None, 0):
                h_dict['change_1d_percent'] = ((price_native - prev_close) / prev_close) * 100
            else:
                h_dict['change_1d_percent'] = None
            h_dict['fx_rate_used'] = fx_rate
            h_dict['current_price_pln'] = price_pln
            h_dict['price_last_updated_at'] = price_updates.get(h_dict['ticker'])
            gross_current_value = h_dict['quantity'] * price_pln
            estimated_sell_fee = PortfolioTradeService._calculate_fx_fee(gross_current_value, currency)
            h_dict['current_value_gross'] = gross_current_value
            h_dict['estimated_sell_fee'] = estimated_sell_fee
            h_dict['current_value'] = gross_current_value - estimated_sell_fee
            h_dict['auto_fx_fees'] = 1 if currency != 'PLN' else h_dict.get('auto_fx_fees', 0)
            h_dict['profit_loss'] = h_dict['current_value'] - h_dict['total_cost']
            h_dict['profit_loss_percent'] = (h_dict['profit_loss'] / h_dict['total_cost'] * 100) if h_dict['total_cost'] != 0 else 0.0
            h_dict['realized_profit'] = open_cycle_realized_profit_by_ticker.get(h_dict['ticker'], 0.0)
            h_dict['break_even_sell_price_pln'] = PortfolioValuationService._calculate_break_even_sell_price_pln(
                h_dict['quantity'],
                h_dict['total_cost'],
                h_dict['realized_profit'],
                currency,
            )
            currency = (h_dict.get('currency') or 'PLN').upper()
            if h_dict['break_even_sell_price_pln'] is not None and fx_rate and (currency == 'PLN' or fx_rate != 1.0):
                h_dict['break_even_sell_price_native'] = h_dict['break_even_sell_price_pln'] / fx_rate
            else:
                h_dict['break_even_sell_price_native'] = None
            holdings_value += h_dict['current_value']
            results.append(h_dict)

        if updates_needed:
            db.commit()

        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        cash = portfolio['current_cash'] if portfolio else 0
        total_portfolio_value = holdings_value + cash
        return PortfolioValuationService.calculate_metrics(results, total_portfolio_value, cash)

    @staticmethod
    def get_portfolio_value(portfolio_id):
        portfolio = PortfolioValuationService.get_portfolio(portfolio_id)
        if not portfolio:
            return None

        db = get_db()
        # Check if this portfolio has children (is it a parent?)
        children = db.execute('SELECT id, name FROM portfolios WHERE parent_portfolio_id = ? AND is_archived = 0', (portfolio_id,)).fetchall()
        
        # Calculate its OWN value (where sub_portfolio_id is NULL)
        own_value_data = PortfolioValuationService._calculate_single_portfolio_value(portfolio)
        
        if not children:
            # It's a single portfolio (or a child)
            return own_value_data

        # It's a parent portfolio - aggregate children values
        breakdown = []
        total_value = own_value_data['portfolio_value']
        total_cash = own_value_data['cash_value']
        total_holdings = own_value_data['holdings_value']
        total_dividends = own_value_data['total_dividends']
        total_interest = own_value_data['total_interest']
        total_open_positions_result = own_value_data['open_positions_result']
        
        # Add parent's own values to breakdown first (if not zero)
        if total_value > 0.001:
            breakdown.append({
                'id': portfolio_id,
                'name': f"{portfolio['name']} (Own)",
                'value': own_value_data['portfolio_value'],
                'is_parent_own': True
            })

        for child in children:
            child_portfolio = PortfolioValuationService.get_portfolio(child['id'])
            child_value_data = PortfolioValuationService._calculate_single_portfolio_value(child_portfolio)
            
            total_value += child_value_data['portfolio_value']
            total_cash += child_value_data['cash_value']
            total_holdings += child_value_data['holdings_value']
            total_dividends += child_value_data['total_dividends']
            total_interest += child_value_data['total_interest']
            total_open_positions_result += child_value_data['open_positions_result']
            
            breakdown.append({
                'id': child['id'],
                'name': child['name'],
                'value': child_value_data['portfolio_value'],
                'is_parent_own': False
            })

        # Calculate share percentage
        if total_value > 0:
            for item in breakdown:
                item['share_pct'] = round((item['value'] / total_value) * 100, 2)
        else:
            for item in breakdown:
                item['share_pct'] = 0.0

        # Merge results (total result and XIRR would need more complex logic for parent, 
        # but for now we follow the "sum children + own" rule)
        # Note: total_result for parent is tricky because of net_contributions.
        # Let's use the same logic as for single but with aggregated totals.
        
        # Aggregate net contributions for all (parent + children)
        net_contributions = 0.0
        portfolio_ids = [portfolio_id] + [c['id'] for c in children]
        
        for p_id in portfolio_ids:
            p = PortfolioValuationService.get_portfolio(p_id)
            if p['account_type'] == 'PPK':
                current_price = None
                try:
                    current_price = PPKService.fetch_current_price()['price']
                except Exception: pass
                ppk_summary = PPKService.get_portfolio_summary(p_id, current_price)
                net_contributions += float(ppk_summary['totalPurchaseValue'])
            else:
                if p.get('parent_portfolio_id'):
                    # To jest dziecko — transakcje są pod parent_id
                    flows = db.execute(
                        '''SELECT
                            COALESCE(SUM(CASE WHEN type='DEPOSIT' THEN total_value ELSE 0 END),0) AS deposits,
                            COALESCE(SUM(CASE WHEN type='WITHDRAW' THEN total_value ELSE 0 END),0) AS withdrawals
                        FROM transactions
                        WHERE portfolio_id = ? AND sub_portfolio_id = ?''',
                        (p['parent_portfolio_id'], p_id)
                    ).fetchone()
                else:
                    # To jest rodzic — tylko jego własne (sub_portfolio_id IS NULL)
                    flows = db.execute(
                        '''SELECT
                            COALESCE(SUM(CASE WHEN type='DEPOSIT' THEN total_value ELSE 0 END),0) AS deposits,
                            COALESCE(SUM(CASE WHEN type='WITHDRAW' THEN total_value ELSE 0 END),0) AS withdrawals
                        FROM transactions
                        WHERE portfolio_id = ? AND sub_portfolio_id IS NULL''',
                        (p_id,)
                    ).fetchone()
                net_contributions += float(flows['deposits']) - float(flows['withdrawals'])

        total_result = total_value - net_contributions
        total_result_percent = (total_result / net_contributions * 100) if net_contributions > 0 else 0.0

        # Aggregated XIRR for parent
        xirr_percent = 0.0
        try:
            # Collect all deposits/withdrawals for parent and all children
            placeholders = ', '.join(['?'] * len(portfolio_ids))
            tx_rows = db.execute(
                f'SELECT date, type, total_value FROM transactions WHERE portfolio_id IN ({placeholders}) AND type IN (?, ?)', 
                tuple(portfolio_ids) + ('DEPOSIT', 'WITHDRAW')
            ).fetchall()
            
            cash_flows = []
            for t in tx_rows:
                try:
                    t_date_str = str(t['date']).split(' ')[0]
                    t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                    amount = float(t['total_value'])
                    if t['type'] == 'DEPOSIT':
                        cash_flows.append((t_date, -amount))
                    elif t['type'] == 'WITHDRAW':
                        cash_flows.append((t_date, amount))
                except Exception: continue
                
            if cash_flows:
                cash_flows.append((date.today(), total_value))
                xirr_percent = xirr(cash_flows)
        except Exception as e:
            print(f"Aggregated XIRR calculation error: {e}")

        return {
            'portfolio_value': total_value,
            'cash_value': total_cash,
            'holdings_value': total_holdings,
            'total_dividends': total_dividends,
            'total_interest': total_interest,
            'open_positions_result': total_open_positions_result,
            'total_result': total_result,
            'total_result_percent': total_result_percent,
            'breakdown': sorted(breakdown, key=lambda x: x['value'], reverse=True),
            'xirr_percent': xirr_percent 
        }

    @staticmethod
    def get_parent_child_consistency_audit():
        db = get_db()
        checked_at = datetime.utcnow().replace(microsecond=0).isoformat()
        parents = db.execute(
            '''
            SELECT p.id, p.name
            FROM portfolios p
            WHERE p.parent_portfolio_id IS NULL
              AND EXISTS (
                  SELECT 1 FROM portfolios c
                  WHERE c.parent_portfolio_id = p.id
              )
            ORDER BY p.id ASC
            '''
        ).fetchall()

        portfolio_rows = []
        summary = {'ok': 0, 'warning': 0, 'error': 0}

        for parent in parents:
            parent_id = int(parent['id'])
            parent_name = parent['name']

            parent_value_data = PortfolioValuationService.get_portfolio_value(parent_id) or {}
            own_value_data = PortfolioValuationService._calculate_single_portfolio_value(
                PortfolioValuationService.get_portfolio(parent_id)
            )
            active_children = db.execute(
                '''
                SELECT id
                FROM portfolios
                WHERE parent_portfolio_id = ? AND is_archived = 0
                ''',
                (parent_id,),
            ).fetchall()
            children_sum = 0.0
            for child in active_children:
                child_portfolio = PortfolioValuationService.get_portfolio(child['id'])
                child_value_data = PortfolioValuationService._calculate_single_portfolio_value(child_portfolio)
                children_sum += float(child_value_data.get('portfolio_value') or 0.0)

            parent_total_value = float(parent_value_data.get('portfolio_value') or 0.0)
            parent_own_value = float(own_value_data.get('portfolio_value') or 0.0)
            expected_value = children_sum + parent_own_value
            diff_pln = round(parent_total_value - expected_value, 2)
            value_match_ok = abs(diff_pln) <= PortfolioValuationService.CONSISTENCY_TOLERANCE_PLN

            orphan_rows = db.execute(
                '''
                SELECT t.id
                FROM transactions t
                LEFT JOIN portfolios c ON c.id = t.sub_portfolio_id
                WHERE t.portfolio_id = ?
                  AND t.sub_portfolio_id IS NOT NULL
                  AND (c.id IS NULL OR c.parent_portfolio_id != ?)
                ORDER BY t.id ASC
                ''',
                (parent_id, parent_id),
            ).fetchall()
            orphan_ids = [int(row['id']) for row in orphan_rows]

            interest_rows = db.execute(
                '''
                SELECT id
                FROM transactions
                WHERE portfolio_id = ?
                  AND type = 'INTEREST'
                  AND sub_portfolio_id IS NOT NULL
                ORDER BY id ASC
                ''',
                (parent_id,),
            ).fetchall()
            interest_ids = [int(row['id']) for row in interest_rows]

            archived_rows = db.execute(
                '''
                SELECT t.id
                FROM transactions t
                JOIN portfolios c ON c.id = t.sub_portfolio_id
                WHERE t.portfolio_id = ?
                  AND c.parent_portfolio_id = ?
                  AND c.is_archived = 1
                  AND c.archived_at IS NOT NULL
                  AND date(t.date) > date(c.archived_at)
                ORDER BY t.id ASC
                ''',
                (parent_id, parent_id),
            ).fetchall()
            archived_ids = [int(row['id']) for row in archived_rows]

            parent_cash_negative_days = PortfolioValuationService._compute_cash_negative_days(parent_id, parent_id)

            checks = {
                'value_match': {
                    'ok': value_match_ok,
                    'diff_pln': diff_pln,
                },
                'orphan_transactions': {
                    'ok': len(orphan_ids) == 0,
                    'count': len(orphan_ids),
                    'ids': orphan_ids,
                },
                'interest_leaked': {
                    'ok': len(interest_ids) == 0,
                    'count': len(interest_ids),
                    'ids': interest_ids,
                },
                'archived_child_transactions': {
                    'ok': len(archived_ids) == 0,
                    'count': len(archived_ids),
                    'ids': archived_ids,
                },
                'cash_negative_days': parent_cash_negative_days,
            }

            has_error = not checks['orphan_transactions']['ok'] or not checks['interest_leaked']['ok'] or not checks['archived_child_transactions']['ok']
            has_warning = (not checks['value_match']['ok']) or (not checks['cash_negative_days']['ok'])
            if has_error:
                status = 'error'
            elif has_warning:
                status = 'warning'
            else:
                status = 'ok'
            summary[status] += 1

            portfolio_rows.append({
                'portfolio_id': parent_id,
                'portfolio_name': parent_name,
                'status': status,
                'checks': checks,
            })

            for child in active_children:
                child_id = int(child['id'])
                child_portfolio = PortfolioValuationService.get_portfolio(child_id)
                child_cash_negative_days = PortfolioValuationService._compute_cash_negative_days(parent_id, child_id)

                child_checks = {
                    'value_match': {
                        'ok': True,
                        'diff_pln': 0.0,
                    },
                    'orphan_transactions': {
                        'ok': True,
                        'count': 0,
                        'ids': [],
                    },
                    'interest_leaked': {
                        'ok': True,
                        'count': 0,
                        'ids': [],
                    },
                    'archived_child_transactions': {
                        'ok': True,
                        'count': 0,
                        'ids': [],
                    },
                    'cash_negative_days': child_cash_negative_days,
                }
                child_status = 'warning' if not child_cash_negative_days['ok'] else 'ok'
                summary[child_status] += 1
                portfolio_rows.append({
                    'portfolio_id': child_id,
                    'portfolio_name': child_portfolio['name'] if child_portfolio else f'Child #{child_id}',
                    'status': child_status,
                    'checks': child_checks,
                })

        return {
            'checked_at': checked_at,
            'portfolios': portfolio_rows,
            'summary': summary,
        }

    @staticmethod
    def _calculate_single_portfolio_value(portfolio):
        # Move the existing logic from get_portfolio_value to this helper
        portfolio_id = portfolio['id']
        account_type = portfolio['account_type']
        current_cash = float(portfolio['current_cash'])
        holdings_value = 0.0
        live_interest = 0.0
        open_positions_result = 0.0
        extra_data = {}
        ppk_total_contribution = None
        ppk_total_result = None

        if account_type == 'SAVINGS':
            last_date_str = portfolio['last_interest_date']
            if last_date_str:
                last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                days = (date.today() - last_date).days
                if days > 0:
                    live_interest = current_cash * (float(portfolio['savings_rate']) / 100) * (days / 365.0)
            total_value = current_cash + live_interest
        elif account_type == 'BONDS':
            bonds = BondService.get_bonds(portfolio_id)
            holdings_value = sum(b['total_value'] for b in bonds)
            total_value = current_cash + holdings_value
        elif account_type == 'PPK':
            try:
                current_price = PPKService.fetch_current_price()['price']
            except Exception:
                current_price = None
            ppk_summary = PPKService.get_portfolio_summary(portfolio_id, current_price)
            holdings_value = ppk_summary['totalNetValue']
            total_value = current_cash + holdings_value
            ppk_total_contribution = float(ppk_summary['totalPurchaseValue'])
            ppk_total_result = float(ppk_summary['netProfit'])
            extra_data = ppk_summary
        else:
            # For standard/IKE, we only get OWN holdings (sub_portfolio_id IS NULL)
            holdings = PortfolioValuationService.get_holdings(portfolio_id, aggregate=False)
            holdings_value = sum(float(h.get('current_value', 0.0) or 0.0) for h in holdings)
            open_positions_result = sum(float(h.get('profit_loss', 0.0) or 0.0) for h in holdings)
            total_value = current_cash + holdings_value

            # Calculate 1D and 7D changes for STANDARD/IKE portfolios
            if account_type in ['STANDARD', 'IKE'] and holdings:
                # (Existing logic for 1D/7D changes...)
                tickers = [h['ticker'] for h in holdings]
                currencies = {h.get('currency') or 'PLN' for h in holdings}
                fx_tickers = [f"{c.upper()}PLN=X" for c in currencies if c.upper() != 'PLN']
                
                all_needed_tickers = tickers + fx_tickers
                quotes = PriceService.get_quotes(all_needed_tickers)
                
                holdings_value_now = 0.0
                holdings_value_1d = 0.0
                holdings_value_7d = 0.0
                
                for h in holdings:
                    ticker = h['ticker']
                    currency = (h.get('currency') or 'PLN').upper()
                    qty = float(h['quantity'])
                    
                    q = quotes.get(ticker, {})
                    p_now = q.get('price') or float(h.get('current_price', 0))
                    p_1d = q.get('prev_close') or p_now
                    p_7d = q.get('price_7d_ago') or p_now
                    
                    fx_q = quotes.get(f"{currency}PLN=X", {}) if currency != 'PLN' else {'price': 1.0, 'prev_close': 1.0, 'price_7d_ago': 1.0}
                    fx_now = fx_q.get('price') or 1.0
                    fx_1d = fx_q.get('prev_close') or fx_now
                    fx_7d = fx_q.get('price_7d_ago') or fx_now
                    
                    fee_rate = 0.005 if currency != 'PLN' else 0.0
                    
                    val_now = (qty * p_now * fx_now) * (1.0 - fee_rate)
                    val_1d = (qty * p_1d * fx_1d) * (1.0 - fee_rate)
                    val_7d = (qty * p_7d * fx_7d) * (1.0 - fee_rate)
                    
                    holdings_value_now += val_now
                    holdings_value_1d += val_1d
                    holdings_value_7d += val_7d
                
                if holdings_value_1d > 0:
                    extra_data['change_1d'] = holdings_value_now - holdings_value_1d
                    extra_data['change_1d_percent'] = (extra_data['change_1d'] / holdings_value_1d) * 100
                
                if holdings_value_7d > 0:
                    extra_data['change_7d'] = holdings_value_now - holdings_value_7d
                    extra_data['change_7d_percent'] = (extra_data['change_7d'] / holdings_value_7d) * 100

        db = get_db()
        # Dividends for this specific portfolio (parent's own or child's own)
        # Check if we should filter by sub_portfolio_id here?
        # If it's a child, its portfolio_id is NOT the parent's. 
        # Wait, business rules say: "transactions.portfolio_id always points to parent".
        # But `portfolios` table has `parent_portfolio_id`.
        # If it's a child, it HAS an entry in `portfolios` table.
        # So `dividends` for a child should have its own `portfolio_id`?
        # No, rule 7: "dividends.portfolio_id always points to parent. dividends.sub_portfolio_id is the only source of child assignment."
        
        # This means for a child portfolio, we must query dividends where sub_portfolio_id = child.id
        if portfolio.get('parent_portfolio_id'):
            # It's a child
            div_query = 'SELECT SUM(amount) as total_div FROM dividends WHERE portfolio_id = ? AND sub_portfolio_id = ?'
            div_params = (portfolio['parent_portfolio_id'], portfolio['id'])
            interest_query = "SELECT COALESCE(SUM(total_value), 0) AS total_interest FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id = ? AND type = 'INTEREST'"
            interest_params = (portfolio['parent_portfolio_id'], portfolio['id'])
            flows_query = '''SELECT
                   COALESCE(SUM(CASE WHEN type = 'DEPOSIT' THEN total_value ELSE 0 END), 0) AS deposits,
                   COALESCE(SUM(CASE WHEN type = 'WITHDRAW' THEN total_value ELSE 0 END), 0) AS withdrawals
               FROM transactions
               WHERE portfolio_id = ? AND sub_portfolio_id = ?'''
            flows_params = (portfolio['parent_portfolio_id'], portfolio['id'])
        else:
            # It's a parent (or a single portfolio)
            div_query = 'SELECT SUM(amount) as total_div FROM dividends WHERE portfolio_id = ? AND sub_portfolio_id IS NULL'
            div_params = (portfolio_id,)
            interest_query = "SELECT COALESCE(SUM(total_value), 0) AS total_interest FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id IS NULL AND type = 'INTEREST'"
            interest_params = (portfolio_id,)
            flows_query = '''SELECT
                   COALESCE(SUM(CASE WHEN type = 'DEPOSIT' THEN total_value ELSE 0 END), 0) AS deposits,
                   COALESCE(SUM(CASE WHEN type = 'WITHDRAW' THEN total_value ELSE 0 END), 0) AS withdrawals
               FROM transactions
               WHERE portfolio_id = ? AND sub_portfolio_id IS NULL'''
            flows_params = (portfolio_id,)

        div_result = db.execute(div_query, div_params).fetchone()
        total_dividends = div_result['total_div'] or 0.0
        interest_result = db.execute(interest_query, interest_params).fetchone()
        total_interest = interest_result['total_interest'] or 0.0
        flows_result = db.execute(flows_query, flows_params).fetchone()
        
        net_contributions = float(flows_result['deposits']) - float(flows_result['withdrawals'])
        if account_type == 'PPK':
            net_contributions = ppk_total_contribution or 0.0

        total_result = ppk_total_result if (account_type == 'PPK' and ppk_total_result is not None) else (total_value - net_contributions)
        total_result_percent = (total_result / net_contributions * 100) if net_contributions > 0 else 0.0

        xirr_percent = 0.0
        try:
            # Collect cash flows for this specific portfolio (parent's own or child)
            tx_rows = db.execute(flows_query, flows_params).fetchall() # Wait, flows_query only returns SUMs.
            
            # We need the individual transactions for XIRR
            if portfolio.get('parent_portfolio_id'):
                xirr_tx_query = 'SELECT date, type, total_value FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id = ? AND type IN (?, ?)'
                xirr_tx_params = (portfolio['parent_portfolio_id'], portfolio['id'], 'DEPOSIT', 'WITHDRAW')
            else:
                xirr_tx_query = 'SELECT date, type, total_value FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id IS NULL AND type IN (?, ?)'
                xirr_tx_params = (portfolio_id, 'DEPOSIT', 'WITHDRAW')
                
            tx_rows = db.execute(xirr_tx_query, xirr_tx_params).fetchall()
            
            cash_flows = []
            for t in tx_rows:
                try:
                    t_date_str = str(t['date']).split(' ')[0]
                    t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                    amount = float(t['total_value'])
                    if t['type'] == 'DEPOSIT':
                        cash_flows.append((t_date, -amount))
                    elif t['type'] == 'WITHDRAW':
                        cash_flows.append((t_date, amount))
                except Exception: continue
                
            if cash_flows:
                cash_flows.append((date.today(), total_value))
                xirr_percent = xirr(cash_flows)
        except Exception as e:
            print(f"Single XIRR calculation error for {portfolio_id}: {e}")

        result = {
            'portfolio_value': total_value,
            'cash_value': current_cash + live_interest,
            'holdings_value': holdings_value,
            'total_dividends': total_dividends,
            'total_interest': total_interest,
            'open_positions_result': open_positions_result,
            'total_result': total_result,
            'total_result_percent': total_result_percent,
            'xirr_percent': xirr_percent,
            'live_interest': live_interest
        }

        if extra_data:
            result.update(extra_data)
        return result

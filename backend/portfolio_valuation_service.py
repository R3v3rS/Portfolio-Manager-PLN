from price_service import PriceService
from database import get_db
from datetime import datetime, date
from bond_service import BondService
from math_utils import xirr
from modules.ppk.ppk_service import PPKService
from portfolio_core_service import PortfolioCoreService
from portfolio_trade_service import PortfolioTradeService


class PortfolioValuationService(PortfolioCoreService):
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
    def get_holdings(portfolio_id, force_price_refresh=False):
        db = get_db()
        holdings = db.execute('SELECT * FROM holdings WHERE portfolio_id = ?', (portfolio_id,)).fetchall()
        results = []
        if not holdings:
            return results

        tickers = [h['ticker'] for h in holdings]
        current_prices = PriceService.get_prices(tickers, force_refresh=force_price_refresh)
        price_updates = PriceService.get_price_updates(tickers)
        fx_rates = PortfolioTradeService._get_fx_rates_to_pln({h['currency'] or 'PLN' for h in holdings})
        updates_needed = False
        holdings_value = 0.0

        for h in holdings:
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
            holdings = PortfolioValuationService.get_holdings(portfolio_id)
            holdings_value = sum(float(h.get('current_value', 0.0) or 0.0) for h in holdings)
            open_positions_result = sum(float(h.get('profit_loss', 0.0) or 0.0) for h in holdings)
            total_value = current_cash + holdings_value

        db = get_db()
        div_result = db.execute('SELECT SUM(amount) as total_div FROM dividends WHERE portfolio_id = ?', (portfolio_id,)).fetchone()
        total_dividends = div_result['total_div'] or 0.0
        interest_result = db.execute("SELECT COALESCE(SUM(total_value), 0) AS total_interest FROM transactions WHERE portfolio_id = ? AND type = 'INTEREST'", (portfolio_id,)).fetchone()
        total_interest = interest_result['total_interest'] or 0.0
        flows_result = db.execute(
            '''SELECT
                   COALESCE(SUM(CASE WHEN type = 'DEPOSIT' THEN total_value ELSE 0 END), 0) AS deposits,
                   COALESCE(SUM(CASE WHEN type = 'WITHDRAW' THEN total_value ELSE 0 END), 0) AS withdrawals
               FROM transactions
               WHERE portfolio_id = ?''',
            (portfolio_id,)
        ).fetchone()
        net_contributions = float(flows_result['deposits']) - float(flows_result['withdrawals'])
        if account_type == 'PPK':
            net_contributions = ppk_total_contribution or 0.0

        total_result = ppk_total_result if (account_type == 'PPK' and ppk_total_result is not None) else (total_value - net_contributions)
        total_result_percent = (total_result / net_contributions * 100) if net_contributions > 0 else 0.0

        xirr_percent = 0.0
        try:
            transactions = db.execute('SELECT date, type, total_value FROM transactions WHERE portfolio_id = ? AND type IN (?, ?)', (portfolio_id, 'DEPOSIT', 'WITHDRAW')).fetchall()
            cash_flows = []
            for t in transactions:
                try:
                    t_date_str = str(t['date']).split(' ')[0]
                    t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                    amount = float(t['total_value'])
                    if t['type'] == 'DEPOSIT':
                        cash_flows.append((t_date, -amount))
                    elif t['type'] == 'WITHDRAW':
                        cash_flows.append((t_date, amount))
                except Exception as e:
                    print(f"Error parsing transaction for XIRR: {e}")
                    continue
            if cash_flows:
                cash_flows.append((date.today(), total_value))
                xirr_percent = xirr(cash_flows)
        except Exception as e:
            print(f"Error calculating XIRR: {e}")
            xirr_percent = 0.0

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

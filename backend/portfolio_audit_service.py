from database import get_db
from portfolio_core_service import PortfolioCoreService
from typing import Optional, Any
from decimal import Decimal
import logging


class PortfolioAuditService(PortfolioCoreService):
    @staticmethod
    def is_portfolio_empty(portfolio_id: int) -> bool:
        db = get_db()
        portfolio = db.execute(
            'SELECT id, current_cash, parent_portfolio_id FROM portfolios WHERE id = ?',
            (portfolio_id,)
        ).fetchone()
        if not portfolio:
            return False

        # If it's a parent, it's not empty if it has children
        if not portfolio['parent_portfolio_id']:
            has_children = db.execute('SELECT 1 FROM portfolios WHERE parent_portfolio_id = ? LIMIT 1', (portfolio_id,)).fetchone() is not None
            if has_children:
                return False

        # Check own assets (using sub_portfolio_id NULL for parents, or just portfolio_id for children)
        if portfolio['parent_portfolio_id']:
            # It's a child
            parent_id = portfolio['parent_portfolio_id']
            child_id = portfolio['id']
            has_transactions = db.execute('SELECT 1 FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id = ? LIMIT 1', (parent_id, child_id)).fetchone() is not None
            has_holdings = db.execute('SELECT 1 FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id = ? LIMIT 1', (parent_id, child_id)).fetchone() is not None
            has_dividends = db.execute('SELECT 1 FROM dividends WHERE portfolio_id = ? AND sub_portfolio_id = ? LIMIT 1', (parent_id, child_id)).fetchone() is not None
        else:
            # It's a parent (own assets)
            has_transactions = db.execute('SELECT 1 FROM transactions WHERE portfolio_id = ? AND sub_portfolio_id IS NULL LIMIT 1', (portfolio_id,)).fetchone() is not None
            has_holdings = db.execute('SELECT 1 FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id IS NULL LIMIT 1', (portfolio_id,)).fetchone() is not None
            has_dividends = db.execute('SELECT 1 FROM dividends WHERE portfolio_id = ? AND sub_portfolio_id IS NULL LIMIT 1', (portfolio_id,)).fetchone() is not None

        has_bonds = db.execute('SELECT 1 FROM bonds WHERE portfolio_id = ? LIMIT 1', (portfolio_id,)).fetchone() is not None
        has_ppk_transactions = db.execute('SELECT 1 FROM ppk_transactions WHERE portfolio_id = ? LIMIT 1', (portfolio_id,)).fetchone() is not None

        return (
            float(portfolio['current_cash'] or 0) == 0.0
            and not has_transactions
            and not has_holdings
            and not has_bonds
            and not has_dividends
            and not has_ppk_transactions
        )

    @staticmethod
    def rebuild_holdings_from_transactions(portfolio_id: int, subportfolio_id: Optional[int] = None) -> dict[str, Any]:
        logging.info("Rebuild started for portfolio %s (sub=%s)", portfolio_id, subportfolio_id)
        db = get_db()
        portfolio = db.execute('SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            raise ValueError('Portfolio not found')
        
        # Determine actual portfolio_id and sub_portfolio_id for filtering
        if portfolio['parent_portfolio_id']:
            # We are rebuilding a child
            actual_portfolio_id = portfolio['parent_portfolio_id']
            actual_sub_portfolio_id = portfolio['id']
        else:
            # We are rebuilding a parent (or its specific subportfolio if provided)
            actual_portfolio_id = portfolio['id']
            actual_sub_portfolio_id = subportfolio_id

        if actual_sub_portfolio_id is not None:
            query = '''SELECT id, ticker, type, quantity, total_value, date
                       FROM transactions
                       WHERE portfolio_id = ? AND sub_portfolio_id = ?
                       ORDER BY date ASC, id ASC'''
            params = (actual_portfolio_id, actual_sub_portfolio_id)
        else:
            query = '''SELECT id, ticker, type, quantity, total_value, date
                       FROM transactions
                       WHERE portfolio_id = ? AND sub_portfolio_id IS NULL
                       ORDER BY date ASC, id ASC'''
            params = (actual_portfolio_id,)

        transactions = db.execute(query, params).fetchall()

        holdings: dict[str, dict[str, Decimal]] = {}
        cash = Decimal('0')
        realized_profit_total = Decimal('0')

        for tx in transactions:
            tx_type = tx['type']
            ticker = tx['ticker']
            quantity = PortfolioAuditService._to_decimal(tx['quantity'])
            total_value = PortfolioAuditService._to_decimal(tx['total_value'])

            if tx_type == 'DEPOSIT':
                cash += total_value
            elif tx_type == 'WITHDRAW':
                cash -= total_value
            elif tx_type == 'DIVIDEND' or tx_type == 'INTEREST':
                cash += total_value
            elif tx_type == 'BUY':
                cash -= total_value
                position = holdings.setdefault(ticker, {'quantity': Decimal('0'), 'total_cost': Decimal('0')})
                position['quantity'] = PortfolioAuditService._quantize_accounting(position['quantity'] + quantity)
                position['total_cost'] = PortfolioAuditService._quantize_accounting(position['total_cost'] + total_value)
            elif tx_type == 'SELL':
                position = holdings.get(ticker)
                if not position or position['quantity'] < quantity:
                    raise ValueError(f"Insufficient quantity for deterministic rebuild of {ticker} in transaction {tx['id']}")
                avg_price = position['total_cost'] / position['quantity']
                cost_basis = PortfolioAuditService._quantize_accounting(avg_price * quantity)
                remaining_quantity = PortfolioAuditService._quantize_accounting(position['quantity'] - quantity)
                remaining_total_cost = PortfolioAuditService._quantize_accounting(position['total_cost'] - cost_basis)
                if remaining_quantity == 0:
                    remaining_total_cost = Decimal('0')
                elif remaining_total_cost < 0:
                    raise ValueError(f"Negative cost basis detected during rebuild for {ticker} in transaction {tx['id']}")
                position['quantity'] = remaining_quantity
                position['total_cost'] = remaining_total_cost
                cash += total_value
                realized_profit_total += total_value - cost_basis
            else:
                raise ValueError(f"Unsupported transaction type for rebuild: {tx_type}")

        rebuilt_holdings: dict[str, dict[str, float]] = {}
        for ticker, position in holdings.items():
            quantity = PortfolioAuditService._quantize_accounting(position['quantity'])
            total_cost = PortfolioAuditService._quantize_accounting(position['total_cost'])
            
            # Skip positions with near-zero quantity (less than 1e-6)
            if quantity < Decimal('0.000001'):
                continue
            avg_price = PortfolioAuditService._quantize_accounting(total_cost / quantity) if quantity else Decimal('0')
            rebuilt_holdings[ticker] = {
                'quantity': PortfolioAuditService._serialize_decimal(quantity, '0.00000001'),
                'total_cost': PortfolioAuditService._serialize_decimal(total_cost),
                'avg_price': PortfolioAuditService._serialize_decimal(avg_price)
            }

        result = {
            'holdings': rebuilt_holdings,
            'cash': PortfolioAuditService._serialize_decimal(PortfolioAuditService._quantize_accounting(cash)),
            'realized_profit_total': PortfolioAuditService._serialize_decimal(PortfolioAuditService._quantize_accounting(realized_profit_total))
        }
        logging.info("Rebuild completed: %s holdings, cash=%s", len(rebuilt_holdings), result['cash'])
        return result

    @staticmethod
    def audit_portfolio_integrity(portfolio_id: int, subportfolio_id: Optional[int] = None) -> dict[str, Any]:
        db = get_db()
        rebuilt = PortfolioAuditService.rebuild_holdings_from_transactions(portfolio_id, subportfolio_id=subportfolio_id)
        
        portfolio = db.execute('SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            raise ValueError('Portfolio not found')
            
        if portfolio['parent_portfolio_id']:
            actual_portfolio_id = portfolio['parent_portfolio_id']
            actual_sub_portfolio_id = portfolio['id']
        else:
            actual_portfolio_id = portfolio['id']
            actual_sub_portfolio_id = subportfolio_id

        if actual_sub_portfolio_id is not None:
            holdings_rows = db.execute(
                'SELECT ticker, quantity, total_cost FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id = ? ORDER BY ticker ASC',
                (actual_portfolio_id, actual_sub_portfolio_id)
            ).fetchall()
        else:
            holdings_rows = db.execute(
                'SELECT ticker, quantity, total_cost FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id IS NULL ORDER BY ticker ASC',
                (actual_portfolio_id,)
            ).fetchall()

        stored_holdings = {
            row['ticker']: {
                'quantity': PortfolioAuditService._to_decimal(row['quantity']),
                'total_cost': PortfolioAuditService._to_decimal(row['total_cost'])
            }
            for row in holdings_rows
        }

        differences: list[dict[str, Any]] = []
        rebuilt_holdings = rebuilt['holdings']
        all_tickers = sorted(set(stored_holdings.keys()) | set(rebuilt_holdings.keys()))
        for ticker in all_tickers:
            rebuilt_holding = rebuilt_holdings.get(ticker)
            stored_holding = stored_holdings.get(ticker)

            rebuilt_quantity = PortfolioAuditService._to_decimal(rebuilt_holding['quantity'] if rebuilt_holding else 0)
            stored_quantity = PortfolioAuditService._to_decimal(stored_holding['quantity'] if stored_holding else 0)
            
            # Use a small epsilon for quantity comparison (1e-6)
            if abs(rebuilt_quantity - stored_quantity) > Decimal('0.000001'):
                differences.append({'type': 'quantity_mismatch', 'ticker': ticker, 'expected': PortfolioAuditService._serialize_decimal(rebuilt_quantity, '0.00000001'), 'actual': PortfolioAuditService._serialize_decimal(stored_quantity, '0.00000001')})

            rebuilt_total_cost = PortfolioAuditService._to_decimal(rebuilt_holding['total_cost'] if rebuilt_holding else 0)
            stored_total_cost = PortfolioAuditService._to_decimal(stored_holding['total_cost'] if stored_holding else 0)
            
            # Use 0.01 as epsilon for cost comparison (currency)
            if abs(rebuilt_total_cost - stored_total_cost) > Decimal('0.01'):
                differences.append({'type': 'total_cost_mismatch', 'ticker': ticker, 'expected': PortfolioAuditService._serialize_decimal(rebuilt_total_cost), 'actual': PortfolioAuditService._serialize_decimal(stored_total_cost)})

        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            raise ValueError('Portfolio not found')
        stored_cash = PortfolioAuditService._to_decimal(portfolio['current_cash'])
        rebuilt_cash = PortfolioAuditService._to_decimal(rebuilt['cash'])
        
        # Use 0.01 as epsilon for cash comparison (currency)
        if abs(stored_cash - rebuilt_cash) > Decimal('0.01'):
            differences.append({'type': 'cash_mismatch', 'expected': PortfolioAuditService._serialize_decimal(rebuilt_cash), 'actual': PortfolioAuditService._serialize_decimal(stored_cash)})

        if differences:
            logging.warning("Integrity mismatch detected for portfolio %s: %s differences", portfolio_id, len(differences))

        return {'is_consistent': len(differences) == 0, 'differences': differences, 'rebuilt_state': rebuilt}

    @staticmethod
    def repair_portfolio_state(portfolio_id: int, subportfolio_id: Optional[int] = None) -> dict[str, Any]:
        db = get_db()
        audit_result = PortfolioAuditService.audit_portfolio_integrity(portfolio_id, subportfolio_id=subportfolio_id)
        rebuilt = audit_result['rebuilt_state']

        portfolio = db.execute('SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            raise ValueError('Portfolio not found')
            
        if portfolio['parent_portfolio_id']:
            actual_portfolio_id = portfolio['parent_portfolio_id']
            actual_sub_portfolio_id = portfolio['id']
        else:
            actual_portfolio_id = portfolio['id']
            actual_sub_portfolio_id = subportfolio_id

        if actual_sub_portfolio_id is not None:
            holdings_rows = db.execute(
                'SELECT id, ticker, quantity, total_cost, average_buy_price, currency, auto_fx_fees, company_name, sector, industry FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id = ?',
                (actual_portfolio_id, actual_sub_portfolio_id)
            ).fetchall()
        else:
            holdings_rows = db.execute(
                'SELECT id, ticker, quantity, total_cost, average_buy_price, currency, auto_fx_fees, company_name, sector, industry FROM holdings WHERE portfolio_id = ? AND sub_portfolio_id IS NULL',
                (actual_portfolio_id,)
            ).fetchall()

        holdings_by_ticker = {row['ticker']: row for row in holdings_rows}
        changes: list[dict[str, Any]] = []

        try:
            for ticker, existing in holdings_by_ticker.items():
                if ticker not in rebuilt['holdings']:
                    db.execute('DELETE FROM holdings WHERE id = ?', (existing['id'],))
                    changes.append({'action': 'deleted_holding', 'ticker': ticker, 'previous': {'quantity': float(existing['quantity']), 'total_cost': float(existing['total_cost'])}})

            for ticker, rebuilt_holding in rebuilt['holdings'].items():
                quantity = rebuilt_holding['quantity']
                total_cost = rebuilt_holding['total_cost']
                avg_price = rebuilt_holding['avg_price']
                existing = holdings_by_ticker.get(ticker)
                if existing:
                    previous = {'quantity': float(existing['quantity']), 'total_cost': float(existing['total_cost']), 'average_buy_price': float(existing['average_buy_price'])}
                    db.execute('''UPDATE holdings SET quantity = ?, total_cost = ?, average_buy_price = ? WHERE id = ?''', (quantity, total_cost, avg_price, existing['id']))
                    changes.append({'action': 'updated_holding', 'ticker': ticker, 'previous': previous, 'current': rebuilt_holding})
                else:
                    metadata = db.execute('SELECT company_name, sector, industry, currency FROM asset_metadata WHERE ticker = ?', (ticker,)).fetchone()
                    db.execute(
                        '''INSERT INTO holdings
                           (portfolio_id, ticker, quantity, average_buy_price, total_cost, auto_fx_fees, currency, company_name, sector, industry, sub_portfolio_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            actual_portfolio_id,
                            ticker,
                            quantity,
                            avg_price,
                            total_cost,
                            1 if metadata and (metadata['currency'] or 'PLN').upper() != 'PLN' else 0,
                            (metadata['currency'] if metadata and metadata['currency'] else 'PLN'),
                            metadata['company_name'] if metadata else None,
                            metadata['sector'] if metadata else None,
                            metadata['industry'] if metadata else None,
                            actual_sub_portfolio_id
                        )
                    )
                    changes.append({'action': 'created_holding', 'ticker': ticker, 'current': rebuilt_holding})

            # Update cash of the specific portfolio (parent's own or child)
            target_id = actual_sub_portfolio_id if actual_sub_portfolio_id else actual_portfolio_id
            previous_cash_row = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (target_id,)).fetchone()
            previous_cash = float(previous_cash_row['current_cash']) if previous_cash_row else 0.0
            db.execute('UPDATE portfolios SET current_cash = ? WHERE id = ?', (rebuilt['cash'], target_id))
            changes.append({'action': 'updated_cash', 'previous': previous_cash, 'current': rebuilt['cash']})
            db.commit()
        except Exception:
            db.rollback()
            raise

        logging.info("Portfolio repaired for portfolio %s with %s changes", portfolio_id, len(changes))
        return {'portfolio_id': portfolio_id, 'changes': changes, 'rebuilt_state': rebuilt, 'repaired': True}

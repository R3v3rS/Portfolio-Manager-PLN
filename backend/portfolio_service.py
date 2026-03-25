from database import get_db
from portfolio_core_service import SymbolMapping, PortfolioCoreService
from portfolio_import_service import PortfolioImportService
from portfolio_trade_service import PortfolioTradeService
from portfolio_valuation_service import PortfolioValuationService
from portfolio_history_service import PortfolioHistoryService
from portfolio_audit_service import PortfolioAuditService


class PortfolioService(
    PortfolioImportService,
    PortfolioTradeService,
    PortfolioValuationService,
    PortfolioHistoryService,
    PortfolioAuditService,
    PortfolioCoreService,
):
    @staticmethod
    def get_transactions(portfolio_id, ticker=None):
        db = get_db()
        query = 'SELECT * FROM transactions WHERE portfolio_id = ?'
        params = [portfolio_id]
        if ticker:
            query += ' AND ticker = ?'
            params.append(ticker)
        query += ' ORDER BY date DESC'
        transactions = db.execute(query, params).fetchall()
        return [{key: t[key] for key in t.keys()} for t in transactions]

    @staticmethod
    def get_all_transactions(ticker=None):
        db = get_db()
        query = '''SELECT t.*, p.name as portfolio_name
               FROM transactions t
               JOIN portfolios p ON t.portfolio_id = p.id'''
        params = []
        if ticker:
            query += ' WHERE t.ticker = ?'
            params.append(ticker)
        query += ' ORDER BY t.date DESC'
        transactions = db.execute(query, params).fetchall()
        return [{key: t[key] for key in t.keys()} for t in transactions]

    @staticmethod
    def get_dividends(portfolio_id):
        db = get_db()
        dividends = db.execute('SELECT * FROM dividends WHERE portfolio_id = ? ORDER BY date DESC', (portfolio_id,)).fetchall()
        return [{key: d[key] for key in d.keys()} for d in dividends]

    @staticmethod
    def get_monthly_dividends(portfolio_id):
        db = get_db()
        query = '''
            SELECT
                strftime('%Y-%m', date) as month_key,
                SUM(amount) as total_amount
            FROM dividends
            WHERE portfolio_id = ?
            GROUP BY month_key
            ORDER BY month_key ASC
        '''
        results = db.execute(query, (portfolio_id,)).fetchall()
        if not results:
            return []
        from datetime import datetime
        formatted_results = []
        for r in results:
            month_date = datetime.strptime(r['month_key'], '%Y-%m')
            formatted_results.append({'label': month_date.strftime('%b %Y'), 'amount': float(r['total_amount']), 'key': r['month_key']})
        return formatted_results

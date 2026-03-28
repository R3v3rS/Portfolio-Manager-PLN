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
    def get_transactions(portfolio_id, ticker=None, sub_portfolio_id=None, transaction_type=None):
        db = get_db()
        portfolio = db.execute(
            'SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?',
            (portfolio_id,),
        ).fetchone()
        if not portfolio:
            return []

        if portfolio['parent_portfolio_id']:
            where_clause = 't.portfolio_id = ? AND t.sub_portfolio_id = ?'
            params = [portfolio['parent_portfolio_id'], portfolio['id']]
        else:
            where_clause = 't.portfolio_id = ? AND t.sub_portfolio_id IS NULL'
            params = [portfolio['id']]

        query = '''
            SELECT t.*, sp.name as sub_portfolio_name
            FROM transactions t
            LEFT JOIN portfolios sp ON t.sub_portfolio_id = sp.id
            WHERE {where_clause}
        '''
        query = query.format(where_clause=where_clause)
        if ticker:
            query += ' AND t.ticker = ?'
            params.append(ticker)
        if sub_portfolio_id is not None:
            if sub_portfolio_id == 'none':
                query += ' AND t.sub_portfolio_id IS NULL'
            else:
                query += ' AND t.sub_portfolio_id = ?'
                params.append(sub_portfolio_id)
        if transaction_type:
            query += ' AND t.type = ?'
            params.append(transaction_type)
            
        query += ' ORDER BY t.date DESC'
        transactions = db.execute(query, params).fetchall()
        return [{key: t[key] for key in t.keys()} for t in transactions]

    @staticmethod
    def get_all_transactions(ticker=None, portfolio_id=None, sub_portfolio_id=None, transaction_type=None):
        db = get_db()
        query = '''SELECT t.*, p.name as portfolio_name, sp.name as sub_portfolio_name
               FROM transactions t
               JOIN portfolios p ON t.portfolio_id = p.id
               LEFT JOIN portfolios sp ON t.sub_portfolio_id = sp.id
               WHERE 1=1'''
        params = []
        if ticker:
            query += ' AND t.ticker = ?'
            params.append(ticker)
        if portfolio_id:
            query += ' AND t.portfolio_id = ?'
            params.append(portfolio_id)
        if sub_portfolio_id is not None:
            if sub_portfolio_id == 'none':
                query += ' AND t.sub_portfolio_id IS NULL'
            else:
                query += ' AND t.sub_portfolio_id = ?'
                params.append(sub_portfolio_id)
        if transaction_type:
            query += ' AND t.type = ?'
            params.append(transaction_type)
            
        query += ' ORDER BY t.date DESC'
        transactions = db.execute(query, params).fetchall()
        return [{key: t[key] for key in t.keys()} for t in transactions]

    @staticmethod
    def get_dividends(portfolio_id):
        db = get_db()
        portfolio = db.execute(
            'SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?',
            (portfolio_id,),
        ).fetchone()
        if not portfolio:
            return []

        if portfolio['parent_portfolio_id']:
            query = '''
                SELECT d.*, sp.name AS sub_portfolio_name
                FROM dividends d
                LEFT JOIN portfolios sp ON d.sub_portfolio_id = sp.id
                WHERE d.portfolio_id = ? AND d.sub_portfolio_id = ?
                ORDER BY d.date DESC
            '''
            params = (portfolio['parent_portfolio_id'], portfolio['id'])
        else:
            query = '''
                SELECT d.*, sp.name AS sub_portfolio_name
                FROM dividends d
                LEFT JOIN portfolios sp ON d.sub_portfolio_id = sp.id
                WHERE d.portfolio_id = ?
                  AND (
                      d.sub_portfolio_id IS NULL
                      OR d.sub_portfolio_id IN (
                          SELECT id FROM portfolios WHERE parent_portfolio_id = ?
                      )
                  )
                ORDER BY d.date DESC
            '''
            params = (portfolio['id'], portfolio['id'])

        dividends = db.execute(query, params).fetchall()
        return [{key: d[key] for key in d.keys()} for d in dividends]

    @staticmethod
    def get_monthly_dividends(portfolio_id):
        db = get_db()
        portfolio = db.execute(
            'SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?',
            (portfolio_id,),
        ).fetchone()
        if not portfolio:
            return []

        if portfolio['parent_portfolio_id']:
            where_clause = 'WHERE portfolio_id = ? AND sub_portfolio_id = ?'
            params = (portfolio['parent_portfolio_id'], portfolio['id'])
        else:
            where_clause = 'WHERE portfolio_id = ?'
            params = (portfolio['id'],)

        query = '''
            SELECT
                strftime('%Y-%m', date) as month_key,
                SUM(amount) as total_amount
            FROM dividends
            {where_clause}
            GROUP BY month_key
            ORDER BY month_key ASC
        '''.format(where_clause=where_clause)
        results = db.execute(query, params).fetchall()
        if not results:
            return []
        from datetime import datetime
        formatted_results = []
        for r in results:
            month_date = datetime.strptime(r['month_key'], '%Y-%m')
            formatted_results.append({'label': month_date.strftime('%b %Y'), 'amount': float(r['total_amount']), 'key': r['month_key']})
        return formatted_results

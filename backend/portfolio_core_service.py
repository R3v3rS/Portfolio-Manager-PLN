from database import get_db
from datetime import datetime, date
from modules.ppk.ppk_service import PPKService
from dataclasses import dataclass
from typing import Optional, Any
from decimal import Decimal, ROUND_HALF_UP
from difflib import get_close_matches


@dataclass
class SymbolMapping:
    id: int
    symbol_input: str
    ticker: str
    currency: Optional[str]
    created_at: str


class PortfolioCoreService:
    FX_FEE_RATE = 0.005
    ACCOUNTING_PRECISION = Decimal('0.00000001')
    ACCOUNTING_OUTPUT_PRECISION = Decimal('0.01')

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal('0')
        return Decimal(str(value))

    @staticmethod
    def _quantize_accounting(value: Decimal) -> Decimal:
        return value.quantize(PortfolioCoreService.ACCOUNTING_PRECISION, rounding=ROUND_HALF_UP)

    @staticmethod
    def _serialize_decimal(value: Decimal, places: str = '0.01') -> float:
        return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))

    @staticmethod
    def _normalize_symbol_input(symbol_input: str) -> str:
        return ' '.join(str(symbol_input or '').strip().upper().split())

    @staticmethod
    def get_tax_limits():
        db = get_db()
        current_year = date.today().year
        limits = {2026: {'IKE': 28260.0, 'IKZE': 11304.0}}
        year_limits = limits.get(current_year, limits[2026])
        ike_limit = year_limits['IKE']
        ikze_limit = year_limits['IKZE']

        ike_deposited = 0.0
        portfolios = db.execute("SELECT id FROM portfolios WHERE upper(name) LIKE '%IKE%'").fetchall()
        for p in portfolios:
            res = db.execute("""
                SELECT SUM(total_value) as total
                FROM transactions
                WHERE portfolio_id = ?
                AND type = 'DEPOSIT'
                AND date >= ?
            """, (p['id'], f"{current_year}-01-01")).fetchone()
            if res and res['total']:
                ike_deposited += float(res['total'])

        ikze_deposited = 0.0
        portfolios = db.execute("SELECT id FROM portfolios WHERE upper(name) LIKE '%IKZE%'").fetchall()
        for p in portfolios:
            res = db.execute("""
                SELECT SUM(total_value) as total
                FROM transactions
                WHERE portfolio_id = ?
                AND type = 'DEPOSIT'
                AND date >= ?
            """, (p['id'], f"{current_year}-01-01")).fetchone()
            if res and res['total']:
                ikze_deposited += float(res['total'])

        return {
            "year": current_year,
            "IKE": {
                "deposited": ike_deposited,
                "limit": ike_limit,
                "percentage": round((ike_deposited / ike_limit * 100), 2) if ike_limit > 0 else 0.0
            },
            "IKZE": {
                "deposited": ikze_deposited,
                "limit": ikze_limit,
                "percentage": round((ikze_deposited / ikze_limit * 100), 2) if ikze_limit > 0 else 0.0
            }
        }

    @staticmethod
    def create_portfolio(name, initial_cash=0.0, account_type='STANDARD', created_at=None, parent_portfolio_id=None):
        db = get_db()
        cursor = db.cursor()
        try:
            if not created_at:
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if ' ' not in created_at:
                created_at = f"{created_at} 00:00:00"
            interest_date = created_at.split(' ')[0] if ' ' in created_at else created_at
            cursor.execute(
                '''INSERT INTO portfolios (name, current_cash, total_deposits, account_type, last_interest_date, created_at, parent_portfolio_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (name, initial_cash, initial_cash, account_type, interest_date, created_at, parent_portfolio_id)
            )
            portfolio_id = cursor.lastrowid
            if account_type == 'PPK':
                PPKService.create_portfolio_entry(portfolio_id, name, created_at)
            if initial_cash > 0:
                cursor.execute(
                    '''INSERT INTO transactions 
                       (portfolio_id, ticker, type, quantity, price, total_value, date) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, 'CASH', 'DEPOSIT', 1, initial_cash, initial_cash, created_at)
                )
            db.commit()
            return portfolio_id
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_portfolio(portfolio_id):
        db = get_db()
        portfolio = db.execute('SELECT * FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if portfolio:
            p = {key: portfolio[key] for key in portfolio.keys()}
            if p.get('last_interest_date'):
                p['last_interest_date'] = str(p['last_interest_date'])
            if p.get('created_at'):
                p['created_at'] = str(p['created_at'])
            return p
        return None

    @staticmethod
    def list_portfolios(include_children=True):
        from portfolio_audit_service import PortfolioAuditService

        db = get_db()
        try:
            # Fetch all portfolios
            rows = db.execute('SELECT * FROM portfolios').fetchall()
            
            # Convert to list of dicts
            all_portfolios = []
            for row in rows:
                p = {key: row[key] for key in row.keys()}
                if p.get('last_interest_date'):
                    p['last_interest_date'] = str(p['last_interest_date'])
                if p.get('created_at'):
                    p['created_at'] = str(p['created_at'])
                p['is_empty'] = PortfolioAuditService.is_portfolio_empty(p['id'])
                p['children'] = [] # Placeholder for tree structure
                all_portfolios.append(p)
            
            if not include_children:
                return all_portfolios

            # Build tree structure
            portfolio_map = {p['id']: p for p in all_portfolios}
            roots = []
            
            for p in all_portfolios:
                parent_id = p.get('parent_portfolio_id')
                if parent_id and parent_id in portfolio_map:
                    portfolio_map[parent_id]['children'].append(p)
                else:
                    roots.append(p)
                    
            return roots
        except Exception as e:
            print(f"DB FETCH ERROR: {e}")
            raise e

    @staticmethod
    def clear_portfolio_data(portfolio_id: int) -> dict[str, Any]:
        db = get_db()
        portfolio = db.execute(
            'SELECT id, name, account_type, parent_portfolio_id FROM portfolios WHERE id = ?',
            (portfolio_id,)
        ).fetchone()
        if not portfolio:
            raise ValueError('Portfolio not found')

        if portfolio['parent_portfolio_id']:
            raise ValueError('Czyszczenie sub-portfela nie jest dozwolone. Przenieś transakcje ręcznie.')

        active_children = db.execute(
            '''
            SELECT id
            FROM portfolios
            WHERE parent_portfolio_id = ? AND is_archived = 0
            LIMIT 1
            ''',
            (portfolio_id,),
        ).fetchone()
        if active_children:
            raise ValueError('Najpierw zarchiwizuj sub-portfele.')

        try:
            tx_deleted = db.execute('DELETE FROM transactions WHERE portfolio_id = ?', (portfolio_id,)).rowcount
            holdings_deleted = db.execute('DELETE FROM holdings WHERE portfolio_id = ?', (portfolio_id,)).rowcount
            dividends_deleted = db.execute('DELETE FROM dividends WHERE portfolio_id = ?', (portfolio_id,)).rowcount
            bonds_deleted = db.execute('DELETE FROM bonds WHERE portfolio_id = ?', (portfolio_id,)).rowcount

            db.execute(
                'UPDATE portfolios SET current_cash = 0, total_deposits = 0 WHERE id = ?',
                (portfolio_id,)
            )
            db.commit()

            return {
                'success': True,
                'portfolio_id': portfolio_id,
                'deleted': {
                    'transactions': tx_deleted,
                    'holdings': holdings_deleted,
                    'dividends': dividends_deleted,
                    'bonds': bonds_deleted
                }
            }
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def archive_portfolio(portfolio_id):
        db = get_db()
        try:
            db.execute('UPDATE portfolios SET is_archived = 1 WHERE id = ?', (portfolio_id,))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def delete_portfolio(portfolio_id):
        from portfolio_audit_service import PortfolioAuditService

        db = get_db()
        portfolio = db.execute(
            'SELECT id, current_cash, account_type FROM portfolios WHERE id = ?',
            (portfolio_id,)
        ).fetchone()
        if not portfolio:
            raise ValueError('Portfolio not found')

        if not PortfolioAuditService.is_portfolio_empty(portfolio_id):
            raise ValueError('Only empty portfolios can be deleted')

        try:
            db.execute('DELETE FROM ppk_portfolios WHERE id = ?', (portfolio_id,))
            db.execute('DELETE FROM portfolios WHERE id = ?', (portfolio_id,))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

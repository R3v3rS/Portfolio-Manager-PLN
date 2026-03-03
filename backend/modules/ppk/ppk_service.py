from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import re
from urllib.request import Request, urlopen
from typing import Optional, Dict, Any

from database import get_db
from .ppk_calculation import PPKCalculation
from .ppk_dto import PPKSummaryDTO

PPK_PRICE_URL = 'https://mojefundusze.pl/Fundusze/PPK/Nationale-Nederlanden-DFE-Nasze-Jutro-2055-PPK'

def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))

def _q(value: Decimal, places: str = '0.01') -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))

class PPKService:
    @staticmethod
    def fetch_current_price() -> Dict[str, Any]:
        request = Request(
            PPK_PRICE_URL,
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'text/html',
            },
        )

        with urlopen(request, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')

        date_match = re.search(r'<strong>\s*(\d{4}-\d{2}-\d{2})\s*</strong>', html, re.IGNORECASE)
        price_match = re.search(r'<h1>\s*([0-9\s,\.]+)\s*PLN\s*</h1>', html, re.IGNORECASE)

        if not date_match or not price_match:
            raise ValueError('Nie udało się pobrać aktualnej ceny PPK ze strony źródłowej.')

        price = float(price_match.group(1).replace(' ', '').replace(',', '.'))
        return {
            'price': _q(Decimal(str(price))),
            'date': date_match.group(1),
        }

    @staticmethod
    def get_transactions(portfolio_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            '''SELECT id, portfolio_id, date, employee_units, employer_units, price_per_unit
               FROM ppk_transactions
               WHERE portfolio_id = ?
               ORDER BY date DESC, id DESC''',
            (portfolio_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def add_transaction(portfolio_id: int, tx_date: str, employee_units: float, employer_units: float, price_per_unit: float) -> bool:
        db = get_db()
        if not tx_date:
            tx_date = date.today().isoformat()

        db.execute(
            '''INSERT INTO ppk_transactions
               (portfolio_id, date, employee_units, employer_units, price_per_unit)
               VALUES (?, ?, ?, ?, ?)''',
            (portfolio_id, tx_date, employee_units, employer_units, price_per_unit)
        )
        db.commit()
        return True

    @staticmethod
    def get_portfolio_summary(portfolio_id: int, current_price: Optional[float] = None) -> PPKSummaryDTO:
        transactions = PPKService.get_transactions(portfolio_id)
        
        c_price_decimal = Decimal(str(current_price)) if current_price is not None else None
        
        return PPKCalculation.calculate_metrics(transactions, c_price_decimal)

    @staticmethod
    def create_portfolio_entry(portfolio_id: int, name: str, created_at: str) -> None:
        db = get_db()
        db.execute(
            '''INSERT INTO ppk_portfolios (id, name, created_at)
               VALUES (?, ?, ?)''',
            (portfolio_id, name, created_at)
        )

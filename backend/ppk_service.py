from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import re
from urllib.request import Request, urlopen
from database import get_db

TAX_RATE = Decimal('0.19')
EMPLOYER_WEIGHT = Decimal('0.7')
PPK_PRICE_URL = 'https://mojefundusze.pl/Fundusze/PPK/Nationale-Nederlanden-DFE-Nasze-Jutro-2055-PPK'


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _q(value: Decimal, places: str = '0.01') -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


class PPKService:
    @staticmethod
    def fetch_current_price():
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
    def get_transactions(portfolio_id: int):
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
    def add_transaction(portfolio_id: int, tx_date: str, employee_units: float, employer_units: float, price_per_unit: float):
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
    def calculate_summary(transactions, current_price: float | None = None):
        total_units = Decimal('0')
        weighted_cost = Decimal('0')
        employee_purchase_value = Decimal('0')
        employer_purchase_value = Decimal('0')
        employee_current_value = Decimal('0')
        employer_current_value = Decimal('0')

        effective_price = _to_decimal(current_price) if current_price is not None else None

        for t in transactions:
            employee_units = _to_decimal(t['employee_units'])
            employer_units = _to_decimal(t['employer_units'])
            units = employee_units + employer_units
            price = _to_decimal(t['price_per_unit'])
            employee_amount = employee_units * price
            employer_amount = employer_units * price

            current_leg_price = effective_price if effective_price is not None else price
            employee_leg_current_value = employee_units * current_leg_price
            employer_leg_current_value = employer_units * current_leg_price

            total_units += units
            weighted_cost += units * price
            employee_purchase_value += employee_amount
            employer_purchase_value += employer_amount * EMPLOYER_WEIGHT
            employee_current_value += employee_leg_current_value
            employer_current_value += employer_leg_current_value * EMPLOYER_WEIGHT

        avg_price = (weighted_cost / total_units) if total_units > 0 else Decimal('0')
        weighted_contribution = employee_purchase_value + employer_purchase_value
        current_value = employee_current_value + employer_current_value
        profit = current_value - weighted_contribution
        tax = profit * TAX_RATE if profit > 0 else Decimal('0')
        net_profit = profit - tax

        return {
            'totalUnits': _q(total_units, '0.0001'),
            'averagePrice': _q(avg_price),
            'totalContribution': _q(weighted_contribution),
            'currentValue': _q(current_value),
            'profit': _q(profit),
            'tax': _q(tax),
            'netProfit': _q(net_profit),
        }

    @staticmethod
    def get_portfolio_summary(portfolio_id: int, current_price: float | None = None):
        txs = PPKService.get_transactions(portfolio_id)
        return PPKService.calculate_summary(txs, current_price)

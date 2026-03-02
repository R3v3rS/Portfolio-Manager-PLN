from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from database import get_db

TAX_RATE = Decimal('0.19')
EMPLOYER_WEIGHT = Decimal('0.7')


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _q(value: Decimal, places: str = '0.01') -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


class PPKService:
    @staticmethod
    def get_transactions(portfolio_id: int):
        db = get_db()
        rows = db.execute(
            '''SELECT id, portfolio_id, date, units_purchased, price_per_unit,
                      employee_contribution, employer_contribution
               FROM ppk_transactions
               WHERE portfolio_id = ?
               ORDER BY date DESC, id DESC''',
            (portfolio_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def add_transaction(portfolio_id: int, tx_date: str, units_purchased: float, price_per_unit: float,
                        employee_contribution: float, employer_contribution: float):
        db = get_db()
        if not tx_date:
            tx_date = date.today().isoformat()

        db.execute(
            '''INSERT INTO ppk_transactions
               (portfolio_id, date, units_purchased, price_per_unit, employee_contribution, employer_contribution)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (portfolio_id, tx_date, units_purchased, price_per_unit, employee_contribution, employer_contribution)
        )
        db.commit()
        return True

    @staticmethod
    def calculate_summary(transactions, current_price: float | None = None):
        total_units = Decimal('0')
        weighted_cost = Decimal('0')
        employee_sum = Decimal('0')
        employer_weighted_sum = Decimal('0')

        for t in transactions:
            units = _to_decimal(t['units_purchased'])
            price = _to_decimal(t['price_per_unit'])
            employee = _to_decimal(t['employee_contribution'])
            employer = _to_decimal(t['employer_contribution'])

            total_units += units
            weighted_cost += units * price
            employee_sum += employee
            employer_weighted_sum += employer * EMPLOYER_WEIGHT

        avg_price = (weighted_cost / total_units) if total_units > 0 else Decimal('0')
        weighted_contribution = employee_sum + employer_weighted_sum

        effective_price = _to_decimal(current_price) if current_price is not None else avg_price
        current_value = total_units * effective_price
        profit = current_value - weighted_contribution
        tax = profit * TAX_RATE if profit > 0 else Decimal('0')
        net_profit = profit - tax

        return {
            'total_units': _q(total_units, '0.0001'),
            'average_price': _q(avg_price),
            'weighted_contribution': _q(weighted_contribution),
            'current_value': _q(current_value),
            'profit': _q(profit),
            'tax': _q(tax),
            'net_profit': _q(net_profit),
        }

    @staticmethod
    def get_portfolio_summary(portfolio_id: int, current_price: float | None = None):
        txs = PPKService.get_transactions(portfolio_id)
        return PPKService.calculate_summary(txs, current_price)

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

import database
from portfolio_service import PortfolioService
from watchlist_service import WatchlistService


@dataclass(frozen=True)
class ReferenceData:
    account_id: int
    category_id: int
    envelope_id: int
    fx_envelope_id: int
    simple_portfolio_id: int
    fx_portfolio_id: int
    loan_id: int
    xtb_frame: pd.DataFrame


def seed_reference_data() -> ReferenceData:
    db = database.get_db()

    category_id = db.execute(
        "INSERT INTO envelope_categories (name, icon) VALUES (?, ?)",
        ('Core', '📁'),
    ).lastrowid
    account_id = db.execute(
        "INSERT INTO budget_accounts (name, balance, currency) VALUES (?, ?, ?)",
        ('Main budget', 5000.0, 'PLN'),
    ).lastrowid
    envelope_id = db.execute(
        '''INSERT INTO envelopes (category_id, account_id, name, icon, target_amount, balance, type, target_month, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (category_id, account_id, 'Investments', '💼', 3000.0, 1000.0, 'MONTHLY', '2026-03', 'ACTIVE'),
    ).lastrowid
    fx_envelope_id = db.execute(
        '''INSERT INTO envelopes (category_id, account_id, name, icon, target_amount, balance, type, target_month, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (category_id, account_id, 'Travel FX', '💱', 1200.0, 400.0, 'LONG_TERM', None, 'ACTIVE'),
    ).lastrowid
    db.commit()

    simple_portfolio_id = PortfolioService.create_portfolio('Core Portfolio', 2000.0, 'STANDARD', '2026-01-05 00:00:00')
    PortfolioService.buy_stock(simple_portfolio_id, 'AAA', 5, 100.0, '2026-01-10', commission=10.0)
    db.execute("INSERT INTO stock_prices (ticker, date, close_price) VALUES (?, ?, ?)", ('AAA', '2026-01-31', 110.0))
    db.execute("INSERT INTO stock_prices (ticker, date, close_price) VALUES (?, ?, ?)", ('AAA', '2026-02-28', 120.0))
    db.execute("INSERT INTO dividends (portfolio_id, ticker, amount, date) VALUES (?, ?, ?, ?)", (simple_portfolio_id, 'AAA', 15.0, '2026-02-15'))

    fx_portfolio_id = PortfolioService.create_portfolio('FX Portfolio', 1000.0, 'STANDARD', '2026-02-01 00:00:00')
    db.execute(
        '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, currency, auto_fx_fees)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (fx_portfolio_id, 'EUR_ETF', 4.0, 250.0, 1000.0, 'EUR', 1),
    )
    db.execute(
        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, commission)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (fx_portfolio_id, 'EUR_ETF', 'BUY', 4.0, 250.0, 1000.0, '2026-02-10', 0.0),
    )
    db.execute("INSERT INTO stock_prices (ticker, date, close_price) VALUES (?, ?, ?)", ('EUR_ETF', '2026-02-28', 280.0))
    db.execute("INSERT INTO stock_prices (ticker, date, close_price) VALUES (?, ?, ?)", ('EURPLN=X', '2026-02-28', 4.2))

    loan_id = db.execute(
        '''INSERT INTO loans (name, original_amount, duration_months, start_date, installment_type, category)
           VALUES (?, ?, ?, ?, ?, ?)''',
        ('Mortgage', 120000.0, 24, '2026-01-01', 'EQUAL', 'HIPOTECZNY'),
    ).lastrowid
    db.execute(
        "INSERT INTO loan_rates (loan_id, interest_rate, valid_from_date) VALUES (?, ?, ?)",
        (loan_id, 6.0, '2026-01-01'),
    )
    db.execute(
        "INSERT INTO loan_overpayments (loan_id, amount, date, type) VALUES (?, ?, ?, ?)",
        (loan_id, 5000.0, '2026-03-15', 'REDUCE_INSTALLMENT'),
    )

    WatchlistService.add_to_watchlist('AAA')
    db.execute(
        '''INSERT INTO symbol_mappings (symbol_input, ticker, currency)
           VALUES (?, ?, ?)''',
        ('AAA US', 'AAA', 'PLN'),
    )
    db.commit()

    xtb_frame = pd.DataFrame([
        {'Type': 'Deposit', 'Time': '2026-01-02 10:00:00', 'Amount': '1000', 'Comment': '', 'Symbol': ''},
        {'Type': 'Stock purchase', 'Time': '2026-01-03 10:00:00', 'Amount': '-500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAA US'},
        {'Type': 'Free funds interest', 'Time': '2026-01-04 10:00:00', 'Amount': '2.50', 'Comment': '', 'Symbol': ''},
    ])

    return ReferenceData(
        account_id=account_id,
        category_id=category_id,
        envelope_id=envelope_id,
        fx_envelope_id=fx_envelope_id,
        simple_portfolio_id=simple_portfolio_id,
        fx_portfolio_id=fx_portfolio_id,
        loan_id=loan_id,
        xtb_frame=xtb_frame,
    )

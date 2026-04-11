from flask import Blueprint
from database import get_db
from budget_service import BudgetService
from portfolio_service import PortfolioService
from loan_service import LoanService
from api.response import success_response
from datetime import date, datetime

dashboard_bp = Blueprint('dashboard_bp', __name__)

POLISH_MONTHS = {
    1: "Styczeń",
    2: "Luty",
    3: "Marzec",
    4: "Kwiecień",
    5: "Maj",
    6: "Czerwiec",
    7: "Lipiec",
    8: "Sierpień",
    9: "Wrzesień",
    10: "Październik",
    11: "Listopad",
    12: "Grudzień",
}

@dashboard_bp.route('/global-summary', methods=['GET'])
def global_summary():
    db = get_db()
    
    # 1. Total Cash (Budget Module)
    # Only unallocated funds should count towards dashboard assets/net worth.
    # We therefore use Total Free Pool instead of raw account balances.
    accounts = db.execute("SELECT id FROM budget_accounts").fetchall()
    total_free_pool = 0.0
    for acc in accounts:
        total_free_pool += BudgetService.get_free_pool(acc['id'])
    total_cash = total_free_pool

    # 2. Total Investments (Portfolio Module)
    portfolios = PortfolioService.list_portfolios()
    total_investments = 0.0
    
    # Breakdown variables
    breakdown_cash_budget = total_cash # Free Pool from budget accounts
    breakdown_cash_invest = 0.0
    breakdown_savings = 0.0
    breakdown_bonds = 0.0
    breakdown_stocks = 0.0
    breakdown_ppk = 0.0
    
    for p in portfolios:
        p_val = PortfolioService.get_portfolio_value(p['id'])
        if p_val:
            total_investments += p_val['portfolio_value']
            
            p_type = p.get('account_type', 'STANDARD')
            
            if p_type == 'SAVINGS':
                # For SAVINGS, the entire value is considered "Konta Oszczędnościowe"
                breakdown_savings += p_val['portfolio_value']
            elif p_type == 'PPK':
                # Keep PPK as separate bucket in global assets structure
                breakdown_ppk += p_val['portfolio_value']
            elif p_type == 'BONDS':
                # For BONDS, split cash and holdings
                breakdown_cash_invest += p_val['cash_value']
                breakdown_bonds += p_val['holdings_value']
            else:
                # For STANDARD (Stocks/ETF), split cash and holdings
                breakdown_cash_invest += p_val['cash_value']
                breakdown_stocks += p_val['holdings_value']

    # 3. Total Liabilities (Loans Module)
    loans_rows = db.execute("SELECT id, name, category FROM loans").fetchall()
    total_liabilities = 0.0
    short_term_liabilities = 0.0
    long_term_liabilities = 0.0
    next_installment_amount = 0.0
    next_installment_date = None
    
    today = date.today()
    
    for loan_row in loans_rows:
        loan_id = loan_row['id']
        # We use the schedule generation to get the accurate current remaining balance
        # considering all overpayments/rate changes up to now.
        schedule_data = LoanService.generate_amortization_schedule(loan_id)
        
        if not schedule_data or 'simulation' not in schedule_data:
            continue
            
        schedule = schedule_data['simulation']['schedule']
        
        # Find current balance: last entry where date <= today
        # If today is before start, it's original amount (handled by month 0 in schedule usually)
        
        current_loan_balance = 0.0
        
        # Sort just in case, though usually sorted
        sorted_schedule = sorted(schedule, key=lambda x: x['date'])
        
        # Find the state as of today
        # We look for the last payment that occurred <= today
        past_payments = [p for p in sorted_schedule if p['date'] <= today.isoformat()]
        
        if past_payments:
            current_loan_balance = past_payments[-1]['remaining_balance']
        else:
            # If no payments yet (and month 0 is future?), use loan original amount
            # But LoanService puts Month 0 at start_date.
            if sorted_schedule:
                current_loan_balance = sorted_schedule[0]['remaining_balance'] # Month 0
        
        total_liabilities += current_loan_balance

        category = loan_row['category'] if loan_row['category'] else 'GOTOWKOWY'
        if category == 'HIPOTECZNY':
            long_term_liabilities += current_loan_balance
        else:
            # Short-term: cash loans + 0% installments (and fallback for unknown categories)
            short_term_liabilities += current_loan_balance
        
        # Find next installment
        future_payments = [p for p in sorted_schedule if p['date'] > today.isoformat()]
        if future_payments:
            next_payment = future_payments[0]
            # We want the *soonest* installment across all loans
            np_date = datetime.strptime(next_payment['date'], '%Y-%m-%d').date()
            
            if next_installment_date is None or np_date < next_installment_date:
                next_installment_date = np_date
                next_installment_amount = next_payment['installment']
            elif np_date == next_installment_date:
                next_installment_amount += next_payment['installment']

    # 4. Aggregation
    total_assets = total_cash + total_investments
    net_worth = total_assets - total_liabilities
    
    payload = {
        "net_worth": round(net_worth, 2),
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "liabilities_breakdown": {
            "short_term": round(short_term_liabilities, 2),
            "long_term": round(long_term_liabilities, 2)
        },
        "assets_breakdown": {
            "budget_cash": round(breakdown_cash_budget, 2),
            "invest_cash": round(breakdown_cash_invest, 2),
            "savings": round(breakdown_savings, 2),
            "bonds": round(breakdown_bonds, 2),
            "stocks": round(breakdown_stocks, 2),
            "ppk": round(breakdown_ppk, 2)
        },
        "quick_stats": {
            "free_pool": round(total_free_pool, 2),
            "next_loan_installment": round(next_installment_amount, 2),
            "next_loan_date": next_installment_date.isoformat() if next_installment_date else None
        }
    }
    return success_response(payload)


@dashboard_bp.route('/dividends/current-month', methods=['GET'])
def current_month_dividends():
    db = get_db()
    today = date.today()
    current_month = today.strftime('%Y-%m')

    received_row = db.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS received_this_month
        FROM dividends
        WHERE strftime('%Y-%m', date) = ?
        """,
        (current_month,),
    ).fetchone()
    received_this_month = float(received_row['received_this_month'] or 0.0)

    expected_row = db.execute(
        """
        SELECT COALESCE(
            SUM(
                COALESCE(h.quantity, 0)
                * COALESCE(rc.price, 0)
                * (COALESCE(rc.dividend_yield, 0) / 100.0)
                / 12.0
            ),
            0
        ) AS expected_this_month
        FROM holdings h
        JOIN radar_cache rc ON rc.ticker = h.ticker
        WHERE strftime('%Y-%m', rc.ex_dividend_date) = ?
          AND COALESCE(h.quantity, 0) > 0
        """,
        (current_month,),
    ).fetchone()
    expected_this_month = float(expected_row['expected_this_month'] or 0.0)

    top_payers_rows = db.execute(
        """
        SELECT
            ticker,
            SUM(amount) AS amount,
            MAX(date) AS date
        FROM dividends
        WHERE strftime('%Y-%m', date) = ?
        GROUP BY ticker
        ORDER BY amount DESC
        LIMIT 3
        """,
        (current_month,),
    ).fetchall()

    payload = {
        "received_this_month": round(received_this_month, 2),
        "expected_this_month": round(expected_this_month, 2),
        "month_label": f"{POLISH_MONTHS[today.month]} {today.year}",
        "top_payers": [
            {
                "ticker": row["ticker"],
                "amount": round(float(row["amount"] or 0.0), 2),
                "date": row["date"],
            }
            for row in top_payers_rows
        ],
    }
    return success_response(payload)

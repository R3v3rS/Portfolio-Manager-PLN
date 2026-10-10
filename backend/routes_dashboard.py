from flask import Blueprint, current_app, request
import sqlite3
import json
from contextlib import closing
from database import get_db
from budget_summary_service import monthly_budget_totals
from portfolio_service import PortfolioService
from loan_service import LoanService
from api.response import success_response
from datetime import date, datetime, timezone

dashboard_bp = Blueprint('dashboard_bp', __name__)


@dashboard_bp.get('/monthly-report')
def monthly_report():
    from monthly_report_service import generate
    return success_response(generate(request.args.get('month')))


@dashboard_bp.get('/actions')
def dashboard_actions():
    from dashboard_actions_service import workspace
    return success_response(workspace())


@dashboard_bp.post('/tasks')
def create_dashboard_task():
    from dashboard_actions_service import save_task
    return success_response(save_task(request.get_json(silent=True)), status=201)


@dashboard_bp.put('/tasks/<int:task_id>')
def update_dashboard_task(task_id):
    from dashboard_actions_service import save_task
    return success_response(save_task(request.get_json(silent=True), task_id))


@dashboard_bp.put('/tasks/<int:task_id>/completion')
def complete_dashboard_task(task_id):
    from dashboard_actions_service import complete_task
    return success_response(complete_task(task_id, request.get_json(silent=True)))

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
    
    # Actual money is an asset even when it has been assigned to a monthly plan.
    budget_totals = monthly_budget_totals(db, date.today().strftime('%Y-%m'))
    total_cash = budget_totals['balance']
    total_free_pool = budget_totals['to_plan']

    # 2. Total Investments (Portfolio Module)
    portfolios = PortfolioService.list_portfolios()
    total_investments = 0.0
    
    # Breakdown variables
    breakdown_cash_budget = total_cash
    breakdown_cash_invest = 0.0
    breakdown_savings = 0.0
    breakdown_bonds = 0.0
    breakdown_stocks = 0.0
    breakdown_ppk = 0.0
    valuation_notes = []
    investment_statuses = []
    
    for p in portfolios:
        p_val = PortfolioService.get_portfolio_value(p['id'], cached_prices_only=True)
        if p_val:
            investment_statuses.append(p_val.get('valuation_status', 'ok'))
            valuation_notes.extend(p_val.get('valuation_warnings', []))
            if p_val.get('portfolio_value') is None:
                total_investments += p_val.get('available_value', 0)
                breakdown_cash_invest += p_val['cash_value']
                if p['account_type'] in ('STANDARD', 'IKE', 'IKZE'):
                    breakdown_stocks += max(0, p_val.get('available_value', 0) - p_val['cash_value'])
                continue
            total_investments += p_val['portfolio_value']
            
            p_type = p.get('account_type', 'STANDARD')
            
            if p_type == 'SAVINGS':
                # For SAVINGS, the entire value is considered "Konta Oszczędnościowe"
                breakdown_savings += p_val['portfolio_value']
            elif p_type == 'PPK':
                # Keep PPK as separate bucket in global assets structure
                breakdown_ppk += p_val['portfolio_value']
                from modules.ppk.ppk_service import PPKService
                price = PPKService.get_cached_price()
                valuation_notes.append('PPK w majątku: szacunkowa kwota zwrotu według modelu aplikacji; raport wyników funduszu pokazuje wartość brutto.')
                if not price:
                    valuation_notes.append(f'{p["name"]}: brak zapisanej ceny jednostki.')
                elif (date.today()-date.fromisoformat(price['date'])).days>7:
                    valuation_notes.append(f'{p["name"]}: cena jednostki z {price["date"]}, starsza niż 7 dni.')
            elif p_type == 'BONDS':
                # For BONDS, split cash and holdings
                breakdown_cash_invest += p_val['cash_value']
                breakdown_bonds += p_val['holdings_value']
            else:
                # For STANDARD (Stocks/ETF), split cash and holdings
                breakdown_cash_invest += p_val['cash_value']
                breakdown_stocks += p_val['holdings_value']

    # 3. Total Liabilities (Loans Module)
    loans_rows = db.execute("SELECT id, name, category, exclude_from_net_worth FROM loans").fetchall()
    total_liabilities = 0.0
    short_term_liabilities = 0.0
    long_term_liabilities = 0.0
    excluded_liabilities = []
    all_short_term_liabilities = 0.0
    next_installment_amount = 0.0
    next_installment_date = None
    
    today = date.today()
    
    for loan_row in loans_rows:
        status = LoanService.get_status(loan_row['id'], as_of=today.isoformat())
        if not status:
            continue
        # The loan overview and dashboard use the same projected balance.
        # A bank reconciliation is a dated observation, not a current forecast.
        current_loan_balance = status['estimated_balance']
        if loan_row['category'] != 'HIPOTECZNY':
            all_short_term_liabilities += current_loan_balance
        if loan_row['exclude_from_net_worth']:
            excluded_liabilities.append({'id': loan_row['id'], 'name': loan_row['name'], 'estimated_balance': round(current_loan_balance, 2)})
            valuation_notes.append(f'Kredyt „{loan_row["name"]}” nie jest uwzględniany w majątku netto. Raty nadal są uwzględniane w budżecie i prognozie. Zmiana tego ustawienia wpływa na porównanie majątku w czasie.')
        else:
            total_liabilities += current_loan_balance
            if loan_row['category'] == 'HIPOTECZNY':
                long_term_liabilities += current_loan_balance
            else:
                short_term_liabilities += current_loan_balance
        if status['next_due_date']:
            next_date = date.fromisoformat(status['next_due_date'])
            if next_installment_date is None or next_date < next_installment_date:
                next_installment_date = next_date
                next_installment_amount = status['next_installment']
            elif next_date == next_installment_date:
                next_installment_amount += status['next_installment']

    # 4. Aggregation
    total_assets = total_cash + total_investments
    net_worth = total_assets - total_liabilities
    
    from valuation_quality import combined_status
    valuation_status = combined_status(investment_statuses)
    payload = {
        "valuation_status": valuation_status,
        "available_assets": round(total_assets, 2),
        "net_worth": round(net_worth, 2),
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "excluded_liabilities": excluded_liabilities,
        "all_short_term_liabilities": round(all_short_term_liabilities, 2),
        "liabilities_source": "estimated",
        "liabilities_as_of": today.isoformat(),
        "valuation_notes": list(dict.fromkeys(valuation_notes)),
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
            "expected_income": budget_totals['expected_income'],
            "next_loan_installment": round(next_installment_amount, 2),
            "next_loan_date": next_installment_date.isoformat() if next_installment_date else None
        }
    }
    # Separate connection: recording a chart observation must never commit a financial transaction.
    if valuation_status == 'incomplete':
        payload.update(net_worth=None, total_assets=None)
        return success_response(payload)
    with closing(sqlite3.connect(current_app.config['DATABASE'])) as snapshots:
        snapshots.execute('''INSERT INTO net_worth_snapshots
            (date, net_worth, total_assets, total_liabilities, recorded_at, assets_breakdown, valuation_notes) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET net_worth=excluded.net_worth,
            total_assets=excluded.total_assets, total_liabilities=excluded.total_liabilities,
            recorded_at=excluded.recorded_at, assets_breakdown=excluded.assets_breakdown,
            valuation_notes=excluded.valuation_notes''',
            (today.isoformat(), payload['net_worth'], payload['total_assets'], payload['total_liabilities'], datetime.now(timezone.utc).isoformat(),
             json.dumps(payload['assets_breakdown']),json.dumps(payload['valuation_notes'])))
        snapshots.commit()
    return success_response(payload)


@dashboard_bp.get('/net-worth-history')
def net_worth_history():
    rows = get_db().execute('SELECT date, net_worth, total_assets, total_liabilities FROM net_worth_snapshots ORDER BY date').fetchall()
    return success_response({'history': [dict(row) for row in rows]})


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

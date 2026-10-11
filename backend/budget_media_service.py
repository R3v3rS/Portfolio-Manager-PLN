"""Continuous monthly envelopes: current-month allocation, no consumption periods."""
from collections import defaultdict
import calendar


def allocated_cents(db, reserve, month):
    end=f"{month}-{calendar.monthrange(*map(int,month.split('-')))[1]:02d}"
    actual=db.execute('''SELECT COALESCE(SUM(CASE WHEN e.kind='EXPENSE' THEN l.amount_cents ELSE -l.amount_cents END),0)
        FROM budget_entry_lines_v2 l JOIN budget_entries_v2 e ON e.id=l.entry_id
        WHERE l.category_id=? AND e.date BETWEEN ? AND ? AND
        (e.kind='EXPENSE' OR EXISTS(SELECT 1 FROM budget_purchase_refunds r WHERE r.entry_id=e.id))''',
        (reserve['category_id'],month+'-01',end)).fetchone()[0]
    adjustment=db.execute('SELECT COALESCE(SUM(budget_cost_cents),0) FROM budget_reserve_movements WHERE reserve_id=? AND date BETWEEN ? AND ?',
        (reserve['id'],month+'-01',end)).fetchone()[0]
    return actual+adjustment


def category_targets(db, month):
    from budget_planning_service import reserve_plans
    result = defaultdict(int)
    for row in reserve_plans(db, month):
        if row.get('monthly_amount') is not None and not row.get('open_ended'):
            result[row['category_id']] += round(row['planned'] * 100)
    return result


def category_adjustments(db, month, end, pln_only=False):
    # Expenses already appear in the category ledger. Add allocations, subtract
    # the earmark consumed by payments: the same funds are never a second cost.
    currency = " AND UPPER(COALESCE(a.currency,'PLN'))='PLN'" if pln_only else ''
    return dict(db.execute('''SELECT r.category_id,SUM(m.budget_cost_cents)
        FROM budget_reserve_movements m JOIN budget_reserves r ON r.id=m.reserve_id
        JOIN budget_accounts a ON a.id=m.account_id
        WHERE r.monthly_amount_cents IS NOT NULL AND r.open_ended=0 AND substr(m.date,1,7)>=COALESCE(r.monthly_start_month,substr(r.start_date,1,7)) AND m.date BETWEEN ? AND ?'''+currency+
        ' GROUP BY r.category_id', (month+'-01', end)))

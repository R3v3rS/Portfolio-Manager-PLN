"""Additive household planning schema. Existing money and plans are preserved."""


def initialize(db):
    category_columns = {r['name'] for r in db.execute('PRAGMA table_info(budget_categories_v2)')}
    if 'daily_pace_included' not in category_columns:
        db.execute('ALTER TABLE budget_categories_v2 ADD COLUMN daily_pace_included INTEGER NOT NULL DEFAULT 1 CHECK(daily_pace_included IN (0,1))')
    reserve_columns={r['name'] for r in db.execute('PRAGMA table_info(budget_reserves)')}
    if 'category_id' not in reserve_columns: db.execute('ALTER TABLE budget_reserves ADD COLUMN category_id INTEGER REFERENCES budget_categories_v2(id)')
    if 'monthly_amount_cents' not in reserve_columns:
        db.execute('ALTER TABLE budget_reserves ADD COLUMN monthly_amount_cents INTEGER CHECK(monthly_amount_cents>=0)')
    if 'monthly_start_month' not in reserve_columns:
        db.execute('ALTER TABLE budget_reserves ADD COLUMN monthly_start_month TEXT')
    if 'open_ended' not in reserve_columns:
        db.execute('ALTER TABLE budget_reserves ADD COLUMN open_ended INTEGER NOT NULL DEFAULT 0 CHECK(open_ended IN (0,1))')
    columns = {
        'interval_months': 'INTEGER NOT NULL DEFAULT 1 CHECK(interval_months IN (1,3,12))',
        'end_month': 'TEXT', 'promotion_end': 'TEXT', 'notice_date': 'TEXT',
        'regular_amount_cents': 'INTEGER', 'variable_amount': 'INTEGER NOT NULL DEFAULT 0',
        'reserve_id': 'INTEGER REFERENCES budget_reserves(id)',
        'version': 'INTEGER NOT NULL DEFAULT 1', 'notes': "TEXT NOT NULL DEFAULT ''",
        'request_id': 'TEXT', 'request_payload': 'TEXT',
    }
    existing = {r['name'] for r in db.execute('PRAGMA table_info(budget_bills_v2)')}
    for name, definition in columns.items():
        if name not in existing:
            db.execute(f'ALTER TABLE budget_bills_v2 ADD COLUMN {name} {definition}')
    existing = {r['name'] for r in db.execute('PRAGMA table_info(budget_bill_payments_v2)')}
    if 'planned_amount_cents' not in existing:
        db.execute('ALTER TABLE budget_bill_payments_v2 ADD COLUMN planned_amount_cents INTEGER CHECK(planned_amount_cents>0)')
    for name in ('request_id', 'request_payload'):
        if name not in existing:
            db.execute(f'ALTER TABLE budget_bill_payments_v2 ADD COLUMN {name} TEXT')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS budget_default_plans (
            category_id INTEGER NOT NULL REFERENCES budget_categories_v2(id),
            start_month TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),
            version INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(category_id,start_month)
        );
        CREATE TABLE IF NOT EXISTS budget_plan_copy_requests (
            request_id TEXT PRIMARY KEY, request_payload TEXT NOT NULL, result_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_cancelled_requests (request_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS budget_reserve_operation_receipts (
            request_id TEXT PRIMARY KEY, reserve_id INTEGER REFERENCES budget_reserves(id),
            entry_id INTEGER, kind TEXT NOT NULL, request_payload TEXT NOT NULL,
            result_json TEXT NOT NULL, created_at TEXT NOT NULL,
            cancelled INTEGER NOT NULL DEFAULT 0 CHECK(cancelled IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS budget_entry_requests (
            request_id TEXT PRIMARY KEY, request_payload TEXT NOT NULL,
            entry_id INTEGER REFERENCES budget_entries_v2(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS budget_reserve_plan_history (
            reserve_id INTEGER NOT NULL REFERENCES budget_reserves(id), month TEXT NOT NULL,
            plan_json TEXT NOT NULL, PRIMARY KEY(reserve_id,month)
        );
        CREATE TABLE IF NOT EXISTS budget_settlements (
            entry_id INTEGER PRIMARY KEY REFERENCES budget_entries_v2(id),
            reserve_id INTEGER REFERENCES budget_reserves(id), created_entry INTEGER NOT NULL,
            before_json TEXT, movement_ids TEXT NOT NULL DEFAULT '[]',
            recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_settlement_reversals (
            request_id TEXT PRIMARY KEY, request_payload TEXT NOT NULL,
            entry_id INTEGER NOT NULL, audit_json TEXT NOT NULL, reversed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_month_snapshots (
            month TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_purchase_refunds (
            entry_id INTEGER PRIMARY KEY REFERENCES budget_entries_v2(id),
            purchase_entry_id INTEGER NOT NULL REFERENCES budget_entries_v2(id),
            request_id TEXT NOT NULL UNIQUE, request_payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_refund_purchase ON budget_purchase_refunds(purchase_entry_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bill_request ON budget_bills_v2(request_id) WHERE request_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bill_payment_request ON budget_bill_payments_v2(request_id) WHERE request_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS budget_planning_settings (
            id INTEGER PRIMARY KEY CHECK(id=1), pay_day INTEGER CHECK(pay_day BETWEEN 1 AND 31),
            income_id INTEGER REFERENCES budget_expected_incomes(id),
            spending_account_id INTEGER REFERENCES budget_accounts(id),
            loan_account_id INTEGER REFERENCES budget_accounts(id),
            version INTEGER NOT NULL DEFAULT 1
        );
        INSERT OR IGNORE INTO budget_planning_settings(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS budget_category_policies (
            category_id INTEGER PRIMARY KEY REFERENCES budget_categories_v2(id),
            mode TEXT NOT NULL CHECK(mode IN ('RESET','ROLLOVER','RESERVE')),
            reserve_id INTEGER REFERENCES budget_reserves(id), start_month TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            CHECK((mode='RESERVE' AND reserve_id IS NOT NULL) OR (mode!='RESERVE' AND reserve_id IS NULL))
        );
        CREATE TABLE IF NOT EXISTS budget_reserve_month_plans (
            reserve_id INTEGER NOT NULL REFERENCES budget_reserves(id), month TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(amount_cents>=0), priority INTEGER NOT NULL DEFAULT 2 CHECK(priority BETWEEN 1 AND 3),
            version INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(reserve_id,month)
        );
        CREATE TABLE IF NOT EXISTS budget_month_closings (
            id INTEGER PRIMARY KEY, month TEXT NOT NULL UNIQUE,
            request_id TEXT NOT NULL UNIQUE, request_payload TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_month_closing_items (
            closing_id INTEGER NOT NULL REFERENCES budget_month_closings(id),
            category_id INTEGER NOT NULL REFERENCES budget_categories_v2(id), reserve_id INTEGER REFERENCES budget_reserves(id),
            amount_cents INTEGER NOT NULL CHECK(amount_cents>=0), movement_id INTEGER REFERENCES budget_reserve_movements(id),
            PRIMARY KEY(closing_id,category_id)
        );
        CREATE TABLE IF NOT EXISTS budget_purchase_plans (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
            low_cents INTEGER NOT NULL CHECK(low_cents>0), high_cents INTEGER NOT NULL CHECK(high_cents>0),
            due_date TEXT NOT NULL, account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            category_id INTEGER REFERENCES budget_categories_v2(id), reserve_id INTEGER UNIQUE REFERENCES budget_reserves(id),
            status TEXT NOT NULL CHECK(status IN ('IDEA','PLANNED','CANCELLED')), notes TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1, request_id TEXT NOT NULL UNIQUE, request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            CHECK(low_cents<=amount_cents AND high_cents>=amount_cents)
        );
    ''')
    policy_columns = {r['name'] for r in db.execute('PRAGMA table_info(budget_category_policies)')}
    if 'decision_required' not in policy_columns:
        db.execute('ALTER TABLE budget_category_policies ADD COLUMN decision_required INTEGER NOT NULL DEFAULT 0 CHECK(decision_required IN (0,1))')
    closing_columns = {r['name'] for r in db.execute('PRAGMA table_info(budget_month_closing_items)')}
    if 'destination' not in closing_columns:
        db.execute("ALTER TABLE budget_month_closing_items ADD COLUMN destination TEXT NOT NULL DEFAULT 'RESERVE'")
    from loan_budget_service import initialize as initialize_loan_budget
    initialize_loan_budget(db)
    from budget_rollover_service import freeze_legacy_closings
    freeze_legacy_closings(db)

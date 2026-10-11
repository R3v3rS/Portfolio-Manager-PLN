"""Additive schema for reviewed bank imports, category rules and local receipt OCR."""


def initialize(db):
    additions = {
        'budget_categories_v2': [('is_unassigned', 'INTEGER NOT NULL DEFAULT 0'),
            ('parent_id', 'INTEGER REFERENCES budget_categories_v2(id)'),
            ('version', 'INTEGER NOT NULL DEFAULT 1')],
        'budget_entries_v2': [
            ('classification_status', "TEXT NOT NULL DEFAULT 'GENERAL'"),
            ('cash_effect', 'INTEGER NOT NULL DEFAULT 1 CHECK(cash_effect IN (0,1))'),
            ('version', 'INTEGER NOT NULL DEFAULT 1'),
        ],
        'budget_account_transfers': [
            ('cash_effect', 'INTEGER NOT NULL DEFAULT 1 CHECK(cash_effect IN (0,1))'),
            ('reserve_action', "TEXT NOT NULL DEFAULT 'MOVE' CHECK(reserve_action IN ('MOVE','FUND'))"),
        ],
        'budget_reserve_movements': [('budget_cost_cents', 'INTEGER NOT NULL DEFAULT 0')],
        'budget_account_reconciliations': [
            ('record_type', "TEXT NOT NULL DEFAULT 'RECONCILIATION' CHECK(record_type IN ('RECONCILIATION','OPENING'))"),
            ('opening_balance_cents', 'INTEGER'),
        ],
    }
    for table, columns in additions.items():
        existing = {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
        for name, definition in columns:
            if name not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    # Account creation already identifies the opening balance explicitly. Keep
    # its request identity and cash delta while excluding it from corrections.
    import json
    for row in db.execute("SELECT * FROM budget_account_reconciliations WHERE record_type='RECONCILIATION'").fetchall():
        try:
            payload = json.loads(row['request_payload'])
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and payload.get('operation') == 'CREATE':
            db.execute("UPDATE budget_account_reconciliations SET record_type='OPENING',opening_balance_cents=? WHERE id=?",
                       (row['observed_balance_cents'], row['id']))
    db.executescript('''
        CREATE TABLE IF NOT EXISTS budget_reserve_transfer_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            source_account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            target_account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            reserve_id INTEGER NOT NULL REFERENCES budget_reserves(id),
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            CHECK(source_account_id != target_account_id)
        );
        CREATE TABLE IF NOT EXISTS budget_category_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pattern TEXT NOT NULL,
            match_field TEXT NOT NULL CHECK(match_field IN ('ANY','MERCHANT','DESCRIPTION')),
            match_type TEXT NOT NULL CHECK(match_type IN ('CONTAINS','EQUALS','STARTS_WITH')),
            category_id INTEGER NOT NULL REFERENCES budget_categories_v2(id),
            account_id INTEGER REFERENCES budget_accounts(id),
            priority INTEGER NOT NULL DEFAULT 100,
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_csv_profiles (
            signature TEXT PRIMARY KEY,
            mapping_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_import_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            filename TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            balance_mode TEXT NOT NULL CHECK(balance_mode IN ('HISTORY','APPLY')),
            expected_balance_cents INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            version INTEGER NOT NULL DEFAULT 1,
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            commit_request_id TEXT UNIQUE,
            commit_payload TEXT,
            result_json TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS budget_import_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES budget_import_sessions(id),
            row_number INTEGER NOT NULL,
            source_identity TEXT NOT NULL,
            data_json TEXT NOT NULL,
            action TEXT NOT NULL DEFAULT 'NEW',
            entry_id INTEGER REFERENCES budget_entries_v2(id) ON DELETE SET NULL,
            transfer_id INTEGER REFERENCES budget_account_transfers(id) ON DELETE SET NULL,
            manual_category INTEGER NOT NULL DEFAULT 0,
            UNIQUE(session_id,row_number)
        );
        CREATE TABLE IF NOT EXISTS budget_import_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            source_identity TEXT NOT NULL,
            entry_id INTEGER REFERENCES budget_entries_v2(id) ON DELETE CASCADE,
            transfer_id INTEGER REFERENCES budget_account_transfers(id) ON DELETE CASCADE,
            amount_cents INTEGER NOT NULL,
            date TEXT NOT NULL,
            kind TEXT NOT NULL,
            UNIQUE(account_id,source_identity)
        );
        CREATE TABLE IF NOT EXISTS budget_receipt_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER REFERENCES budget_accounts(id),
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            raw_text TEXT NOT NULL DEFAULT '',
            data_json TEXT NOT NULL,
            warnings_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            version INTEGER NOT NULL DEFAULT 1,
            entry_id INTEGER REFERENCES budget_entries_v2(id) ON DELETE SET NULL,
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            commit_request_id TEXT UNIQUE,
            commit_payload TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_budget_import_rows_session ON budget_import_rows(session_id);
        CREATE INDEX IF NOT EXISTS idx_budget_sources_entry ON budget_import_sources(entry_id);
        CREATE INDEX IF NOT EXISTS idx_budget_receipt_drafts_hash ON budget_receipt_drafts(file_hash);
    ''')

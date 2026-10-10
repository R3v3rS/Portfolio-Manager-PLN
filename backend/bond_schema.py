"""Additive migration; existing bond entries remain explicitly marked as legacy."""
def migrate(db):
    columns = {r[1] for r in db.execute('PRAGMA table_info(bonds)')}
    additions = dict(kind="TEXT NOT NULL DEFAULT 'LEGACY'", quantity="INTEGER NOT NULL DEFAULT 1",
        nominal="REAL", purchase_price="REAL", maturity_date="TEXT", tax_rate="REAL NOT NULL DEFAULT 19",
        redemption_fee="REAL", fee_policy="TEXT NOT NULL DEFAULT 'CAP_INTEREST'", payout_account_id="INTEGER REFERENCES budget_accounts(id)",
        forecast_enabled="INTEGER NOT NULL DEFAULT 0", acquisition="TEXT NOT NULL DEFAULT 'LEGACY'",
        status="TEXT NOT NULL DEFAULT 'ACTIVE'", version="INTEGER NOT NULL DEFAULT 1",
        notes="TEXT NOT NULL DEFAULT ''")
    for name, definition in additions.items():
        if name not in columns: db.execute(f'ALTER TABLE bonds ADD COLUMN {name} {definition}')
    db.execute('''CREATE TABLE IF NOT EXISTS bond_rates (
        bond_id INTEGER NOT NULL REFERENCES bonds(id), period INTEGER NOT NULL,
        rate REAL NOT NULL, PRIMARY KEY(bond_id,period))''')
    db.execute('''CREATE TABLE IF NOT EXISTS bond_events (
        id INTEGER PRIMARY KEY, bond_id INTEGER NOT NULL REFERENCES bonds(id),
        kind TEXT NOT NULL, date TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0,
        period INTEGER, net_amount REAL NOT NULL DEFAULT 0, transaction_id INTEGER REFERENCES transactions(id),
        extra_transaction_id INTEGER REFERENCES transactions(id), notes TEXT NOT NULL DEFAULT '')''')
    db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_bond_coupon ON bond_events(bond_id,period)
        WHERE kind='COUPON' ''')
    db.execute('''CREATE TABLE IF NOT EXISTS bond_requests (
        request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL)''')

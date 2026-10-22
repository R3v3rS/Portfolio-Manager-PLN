"""Additive storage for research, saved analysis and planning (no trade writes)."""
def init_schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS investment_ai_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS investment_ai_runs (
        id TEXT PRIMARY KEY, day TEXT NOT NULL, model TEXT NOT NULL, kind TEXT NOT NULL,
        state TEXT NOT NULL, cost_usd REAL NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
        result TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS investment_ai_sessions (
        id TEXT PRIMARY KEY, portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
        title TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS investment_ai_messages (
        id TEXT PRIMARY KEY REFERENCES investment_ai_runs(id), session_id TEXT NOT NULL REFERENCES investment_ai_sessions(id),
        question TEXT NOT NULL, answer TEXT NOT NULL, created_at TEXT NOT NULL,
        journal_id INTEGER REFERENCES investor_journal(id)
    );
    CREATE INDEX IF NOT EXISTS idx_ai_messages_session ON investment_ai_messages(session_id,created_at);
    CREATE TABLE IF NOT EXISTS investment_strategy_plans (
        portfolio_id INTEGER PRIMARY KEY REFERENCES portfolios(id), value TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS investment_fund_compositions (
        ticker TEXT PRIMARY KEY, constituents TEXT NOT NULL, source_url TEXT NOT NULL,
        source_date TEXT, retrieved_at TEXT NOT NULL, source_kind TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS investment_material_reviews (
        id TEXT PRIMARY KEY REFERENCES investment_ai_runs(id), publication_id INTEGER NOT NULL REFERENCES research_publications(id),
        input_kind TEXT NOT NULL, evidence_text TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS investment_material_confirmations (
        review_id TEXT NOT NULL REFERENCES investment_material_reviews(id), item_index INTEGER NOT NULL,
        idea_id INTEGER NOT NULL REFERENCES research_ideas(id), PRIMARY KEY(review_id,item_index)
    );
    CREATE TABLE IF NOT EXISTS research_publication_text (
        publication_id INTEGER PRIMARY KEY REFERENCES research_publications(id),
        text TEXT NOT NULL, source_url TEXT NOT NULL, captured_at TEXT NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0
    );
    ''')
    columns={r[1] for r in db.execute('PRAGMA table_info(investment_ai_runs)')}
    if 'fingerprint' not in columns:
        db.execute("ALTER TABLE investment_ai_runs ADD COLUMN fingerprint TEXT")

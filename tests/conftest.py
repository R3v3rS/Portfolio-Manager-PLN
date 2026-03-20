import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app as backend_app
import database
from portfolio_service import PortfolioService
from price_service import PriceService
from tests.reference_data import seed_reference_data as build_reference_data


@pytest.fixture()
def app(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(backend_app, "init_db", lambda app: None)
    monkeypatch.setattr(backend_app.PriceService, "warmup_cache", classmethod(lambda cls: None))
    monkeypatch.setattr(PriceService, "warmup_cache", classmethod(lambda cls: None))
    monkeypatch.setattr(
        PriceService,
        "fetch_metadata",
        classmethod(lambda cls, ticker: {
            "currency": "PLN",
            "company_name": ticker,
            "sector": "Test Sector",
            "industry": "Test Industry",
        }),
    )
    monkeypatch.setattr(PriceService, "sync_stock_history", classmethod(lambda cls, ticker, start_date=None: None))
    monkeypatch.setattr(PortfolioService, "_get_fx_rates_to_pln", staticmethod(lambda currencies: {currency: 1.0 for currency in currencies}))
    monkeypatch.setattr(PriceService, "get_prices", classmethod(lambda cls, tickers, force_refresh=False: {ticker: 100.0 for ticker in tickers}))
    monkeypatch.setattr(
        PriceService,
        "get_quotes",
        classmethod(lambda cls, tickers: {
            ticker: {"price": 100.0, "change_1d": 1.2, "change_7d": 2.3, "change_1m": 3.4, "change_1y": 4.5}
            for ticker in tickers
        }),
    )
    monkeypatch.setattr(
        PriceService,
        "fetch_market_events",
        classmethod(lambda cls, tickers: {
            ticker: {"next_earnings": "2026-04-01", "ex_dividend_date": "2026-04-15", "dividend_yield": 0.012}
            for ticker in tickers
        }),
    )

    flask_app = backend_app.create_app()
    flask_app.config.update(TESTING=True, DATABASE=str(db_path))
    with flask_app.app_context():
        database.init_db(flask_app)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seed_reference_data(app):
    with app.app_context():
        return build_reference_data()

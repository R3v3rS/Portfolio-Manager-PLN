#!/usr/bin/env python3
"""Benchmark Portfolio history/valuation services on deterministic in-memory data.

How to add a new benchmarked method:
1) Add an entry in BENCHMARK_METHODS (name + callable).
2) If method needs special cache reset, do it in run_single_method().
3) (Optional) add comparison output mapping in print_comparison().
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from inflation_service import InflationService
from portfolio_history_service import PortfolioHistoryService
from portfolio_trade_service import PortfolioTradeService
from portfolio_valuation_service import PortfolioValuationService
from price_service import PriceService


REPEATS = 5
RNG_SEED = 42


@dataclass(frozen=True)
class Scenario:
    name: str
    transactions: int
    tickers: int
    history_days: int


SCENARIOS: dict[str, Scenario] = {
    "small": Scenario("small", 50, 3, 90),
    "medium": Scenario("medium", 500, 10, 365),
    "large": Scenario("large", 2000, 30, 365),
    "stress": Scenario("stress", 5000, 50, 365),
}


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE portfolios (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            account_type TEXT DEFAULT 'STANDARD',
            current_cash REAL DEFAULT 0.0,
            created_at TEXT,
            parent_portfolio_id INTEGER
        );

        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            total_value REAL NOT NULL,
            sub_portfolio_id INTEGER
        );

        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            average_buy_price REAL NOT NULL,
            total_cost REAL NOT NULL,
            company_name TEXT,
            sector TEXT,
            industry TEXT,
            currency TEXT DEFAULT 'PLN',
            sub_portfolio_id INTEGER
        );

        CREATE TABLE stock_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            close_price REAL NOT NULL,
            UNIQUE(ticker, date)
        );

        CREATE INDEX idx_tx_portfolio ON transactions(portfolio_id);
        CREATE INDEX idx_tx_date ON transactions(date);
        CREATE INDEX idx_holdings_portfolio ON holdings(portfolio_id);
        CREATE INDEX idx_prices_ticker_date ON stock_prices(ticker, date);
        """
    )


def random_walk_prices(rng: random.Random, days: int, start: float = 100.0) -> list[float]:
    p = start
    out = []
    for _ in range(days):
        p = max(1.0, p + rng.uniform(-2.5, 2.5))
        out.append(round(p, 2))
    return out


def generate_data(conn: sqlite3.Connection, scenario: Scenario) -> dict[str, Any]:
    rng = random.Random(RNG_SEED)
    today = date.today()
    start_day = today - timedelta(days=scenario.history_days - 1)
    tickers = [f"TK{i:02d}" for i in range(1, scenario.tickers + 1)]

    conn.execute(
        "INSERT INTO portfolios(id, name, account_type, current_cash, created_at, parent_portfolio_id) VALUES(1, 'Bench', 'STANDARD', 0.0, ?, NULL)",
        (start_day.isoformat(),),
    )

    all_prices: dict[str, list[float]] = {
        t: random_walk_prices(rng, scenario.history_days, start=100.0 + rng.uniform(-15, 15))
        for t in tickers
    }

    for ticker in tickers:
        for i, price in enumerate(all_prices[ticker]):
            d = start_day + timedelta(days=i)
            conn.execute(
                "INSERT INTO stock_prices(ticker, date, close_price) VALUES (?, ?, ?)",
                (ticker, d.isoformat(), price),
            )

    cash = 30_000.0
    positions: dict[str, dict[str, float]] = {}

    weights = [
        ("DEPOSIT", 0.18),
        ("BUY", 0.55),
        ("SELL", 0.19),
        ("DIVIDEND", 0.08),
    ]
    w_sum = sum(w for _, w in weights)
    cdf = []
    run = 0.0
    for t, w in weights:
        run += w / w_sum
        cdf.append((t, run))

    def pick_type() -> str:
        x = rng.random()
        for t, threshold in cdf:
            if x <= threshold:
                return t
        return "BUY"

    for i in range(scenario.transactions):
        day_offset = round(i * (scenario.history_days - 1) / max(1, scenario.transactions - 1))
        tx_date = start_day + timedelta(days=day_offset)
        tx_type = pick_type()

        if tx_type == "SELL" and not any(v["qty"] > 0.02 for v in positions.values()):
            tx_type = "DEPOSIT"

        if tx_type == "BUY" and cash < 150.0:
            tx_type = "DEPOSIT"

        if tx_type == "DEPOSIT":
            total = round(rng.uniform(200.0, 2000.0), 2)
            cash += total
            conn.execute(
                "INSERT INTO transactions(portfolio_id, ticker, date, type, quantity, price, total_value, sub_portfolio_id) VALUES(1, 'CASH', ?, 'DEPOSIT', 0, 1, ?, NULL)",
                (tx_date.isoformat(), total),
            )
            continue

        if tx_type == "DIVIDEND":
            held = [t for t, pos in positions.items() if pos["qty"] > 0.01]
            ticker = rng.choice(held) if held else rng.choice(tickers)
            total = round(rng.uniform(5.0, 120.0), 2)
            cash += total
            conn.execute(
                "INSERT INTO transactions(portfolio_id, ticker, date, type, quantity, price, total_value, sub_portfolio_id) VALUES(1, ?, ?, 'DIVIDEND', 0, 1, ?, NULL)",
                (ticker, tx_date.isoformat(), total),
            )
            continue

        ticker = rng.choice(tickers)
        day_idx = (tx_date - start_day).days
        price = all_prices[ticker][day_idx]

        pos = positions.setdefault(ticker, {"qty": 0.0, "cost": 0.0})

        if tx_type == "BUY":
            budget = min(cash * rng.uniform(0.03, 0.2), rng.uniform(300.0, 3500.0))
            if budget < 100.0:
                budget = min(cash, 100.0)
            qty = round(max(0.01, budget / price), 4)
            total = round(qty * price, 2)
            if total > cash:
                total = round(cash, 2)
                qty = round(max(0.01, total / max(price, 0.01)), 4)
                total = round(qty * price, 2)
            cash -= total
            pos["qty"] += qty
            pos["cost"] += total
            conn.execute(
                "INSERT INTO transactions(portfolio_id, ticker, date, type, quantity, price, total_value, sub_portfolio_id) VALUES(1, ?, ?, 'BUY', ?, ?, ?, NULL)",
                (ticker, tx_date.isoformat(), qty, price, total),
            )
        else:  # SELL
            if pos["qty"] <= 0.01:
                continue
            qty = round(min(pos["qty"], pos["qty"] * rng.uniform(0.1, 0.6)), 4)
            qty = max(0.01, qty)
            total = round(qty * price, 2)
            cash += total
            avg = (pos["cost"] / pos["qty"]) if pos["qty"] > 0 else price
            pos["qty"] = round(max(0.0, pos["qty"] - qty), 4)
            pos["cost"] = round(max(0.0, pos["cost"] - qty * avg), 2)
            conn.execute(
                "INSERT INTO transactions(portfolio_id, ticker, date, type, quantity, price, total_value, sub_portfolio_id) VALUES(1, ?, ?, 'SELL', ?, ?, ?, NULL)",
                (ticker, tx_date.isoformat(), qty, price, total),
            )

    for ticker, pos in positions.items():
        if pos["qty"] <= 0.0001:
            continue
        avg = round(pos["cost"] / pos["qty"], 4)
        conn.execute(
            """
            INSERT INTO holdings(
                portfolio_id, ticker, quantity, average_buy_price, total_cost,
                company_name, sector, industry, currency, sub_portfolio_id
            ) VALUES(1, ?, ?, ?, ?, ?, 'Benchmark', 'Synthetic', 'PLN', NULL)
            """,
            (ticker, round(pos["qty"], 4), avg, round(pos["cost"], 2), f"{ticker} Corp"),
        )

    conn.execute("UPDATE portfolios SET current_cash = ? WHERE id = 1", (round(cash, 2),))
    conn.commit()
    return {"portfolio_id": 1, "tickers": tickers, "start": start_day.isoformat(), "end": today.isoformat()}


def install_mocks(conn: sqlite3.Connection, latest_prices: dict[str, float]) -> None:
    import portfolio_history_service as phs_module
    import portfolio_valuation_service as pvs_module

    phs_module.get_db = lambda: conn
    pvs_module.get_db = lambda: conn

    PriceService.get_prices = staticmethod(lambda tickers, force_refresh=False: {t: latest_prices.get(t, 100.0) for t in tickers})
    PriceService.get_price_updates = staticmethod(lambda tickers: {t: datetime.utcnow().isoformat() for t in tickers})
    PriceService.sync_stock_history = staticmethod(lambda ticker, start_date: None)
    PriceService.get_tickers_requiring_history_sync = staticmethod(lambda tickers, start_date: [])
    PriceService.fetch_metadata = staticmethod(
        lambda ticker: {
            "ticker": ticker,
            "company_name": f"{ticker} Corp",
            "sector": "Benchmark",
            "industry": "Synthetic",
            "currency": "PLN",
        }
    )

    PortfolioTradeService._get_fx_rates_to_pln = staticmethod(lambda currencies: {c: 1.0 for c in currencies})
    InflationService.get_inflation_series = staticmethod(
        lambda start, end: [
            {"date": m.strftime("%Y-%m"), "index_value": 100.0}
            for m in month_range(start, end)
        ]
    )
    PortfolioValuationService.get_portfolio_value = staticmethod(lambda portfolio_id: None)


def month_range(start_yyyy_mm: str, end_yyyy_mm: str) -> list[date]:
    sy, sm = map(int, start_yyyy_mm.split("-"))
    ey, em = map(int, end_yyyy_mm.split("-"))
    y, m = sy, sm
    out = []
    while (y, m) <= (ey, em):
        out.append(date(y, m, 1))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return out


BENCHMARK_METHODS: list[tuple[str, Callable[[int, int], Any]]] = [
    ("get_portfolio_profit_history_daily", lambda pid, days: PortfolioHistoryService.get_portfolio_profit_history_daily(pid, days=days)),
    ("_calculate_historical_metrics", lambda pid, _days: PortfolioHistoryService._calculate_historical_metrics(pid)),
    ("get_holdings", lambda pid, _days: PortfolioValuationService.get_holdings(pid)),
]


def measure_callable(fn: Callable[[], Any]) -> dict[str, float]:
    timings_ms: list[float] = []
    mem_before_mb: list[float] = []
    mem_after_mb: list[float] = []

    for _ in range(REPEATS):
        tracemalloc.start()
        before_current, _ = tracemalloc.get_traced_memory()
        t0 = perf_counter()
        fn()
        dt_ms = (perf_counter() - t0) * 1000.0
        after_current, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        timings_ms.append(dt_ms)
        mem_before_mb.append(before_current / (1024 * 1024))
        mem_after_mb.append(after_current / (1024 * 1024))

    avg_ms = statistics.fmean(timings_ms)
    return {
        "min_ms": min(timings_ms),
        "avg_ms": avg_ms,
        "max_ms": max(timings_ms),
        "ram_before_mb": statistics.fmean(mem_before_mb),
        "ram_after_mb": statistics.fmean(mem_after_mb),
    }


def run_single_method(method_name: str, method_fn: Callable[[int, int], Any], portfolio_id: int, days: int, tx_count: int) -> dict[str, Any]:
    def wrapped() -> Any:
        if method_name == "_calculate_historical_metrics":
            PortfolioHistoryService.clear_cache(portfolio_id)
        return method_fn(portfolio_id, days)

    metrics = measure_callable(wrapped)
    avg_s = metrics["avg_ms"] / 1000.0
    metrics["throughput_tx_s"] = (tx_count / avg_s) if avg_s > 0 else 0.0
    return metrics


def fmt_ms(value: float) -> str:
    return f"{value:6.1f}ms"


def fmt_tx(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", " ")


def print_header() -> None:
    print("═" * 59)
    print("BENCHMARK — Portfolio History & Valuation")
    print(f"Python {sys.version_info.major}.{sys.version_info.minor} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 59)


def print_scenario_report(scenario: Scenario, methods: dict[str, Any]) -> None:
    print(f"Scenariusz: {scenario.name} ({scenario.transactions} txs, {scenario.tickers} tickerów, {scenario.history_days} dni)")
    print("─" * 49)
    for method_name, result in methods.items():
        print(method_name)
        if "failed" in result:
            print(f"FAILED: {result['failed']}")
            continue
        print(f"min: {fmt_ms(result['min_ms'])}  avg: {fmt_ms(result['avg_ms'])}  max: {fmt_ms(result['max_ms'])}")
        if method_name != "get_holdings":
            print(f"throughput: {fmt_tx(result['throughput_tx_s'])} tx/s")
        print(f"RAM avg: {result['ram_before_mb']:.2f}MB -> {result['ram_after_mb']:.2f}MB")
    print()


def pct_change(before: float, after: float) -> tuple[float, str, str]:
    if before == 0:
        return 0.0, "→", "⚪"
    delta = ((after - before) / before) * 100.0
    if delta < 0:
        return abs(delta), "↓", "🟢"
    if delta > 0:
        return abs(delta), "↑", "🔴"
    return 0.0, "→", "⚪"


def print_comparison(current: dict[str, Any], previous: dict[str, Any]) -> None:
    print("PORÓWNANIE vs poprzedni wynik")
    print("─" * 49)
    for scenario_name, scenario_data in current.get("scenarios", {}).items():
        prev_data = previous.get("scenarios", {}).get(scenario_name)
        if not prev_data:
            continue
        print(f"Scenariusz: {scenario_name}")
        for method_name, cur_metrics in scenario_data["methods"].items():
            prev_metrics = prev_data["methods"].get(method_name)
            if not prev_metrics or "failed" in cur_metrics or "failed" in prev_metrics:
                continue
            before = prev_metrics["avg_ms"]
            after = cur_metrics["avg_ms"]
            pct, arrow, badge = pct_change(before, after)
            print(method_name)
            print(f"before: {before:.1f}ms  →  after: {after:.1f}ms  ({arrow} {pct:.0f}% {badge})")
        print()


def run_scenario(scenario: Scenario) -> dict[str, Any]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    data = generate_data(conn, scenario)

    latest_prices = {}
    for row in conn.execute("SELECT ticker, close_price FROM stock_prices WHERE date = ?", (data["end"],)).fetchall():
        latest_prices[row["ticker"]] = float(row["close_price"])

    install_mocks(conn, latest_prices)

    method_results: dict[str, Any] = {}
    for method_name, method_fn in BENCHMARK_METHODS:
        try:
            method_results[method_name] = run_single_method(
                method_name,
                method_fn,
                data["portfolio_id"],
                scenario.history_days,
                scenario.transactions,
            )
        except Exception as exc:
            method_results[method_name] = {"failed": f"{type(exc).__name__}: {exc}"}

    conn.close()
    return {
        "scenario": asdict(scenario),
        "methods": method_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Portfolio history & valuation services")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), help="Run only one scenario")
    parser.add_argument("--save", type=Path, help="Save benchmark JSON results")
    parser.add_argument("--compare", type=Path, help="Compare with previous benchmark JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    selected = [SCENARIOS[args.scenario]] if args.scenario else [SCENARIOS[k] for k in ("small", "medium", "large", "stress")]

    results: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "seed": RNG_SEED,
        "repeats": REPEATS,
        "scenarios": {},
    }

    print_header()
    for scenario in selected:
        scenario_result = run_scenario(scenario)
        results["scenarios"][scenario.name] = scenario_result
        print_scenario_report(scenario, scenario_result["methods"])

    if args.save:
        args.save.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Saved results to: {args.save}")

    if args.compare:
        previous = json.loads(args.compare.read_text(encoding="utf-8"))
        print()
        print_comparison(results, previous)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

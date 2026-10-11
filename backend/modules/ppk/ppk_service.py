from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timezone
import re
import json
import math
import logging
import time
from threading import RLock
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Optional, Dict, Any

from valuation_quality import quote_status
from database import get_db
from .ppk_calculation import PPKCalculation
from .ppk_dto import PPKSummaryDTO

PPK_NN_API_URL = 'https://www.nn.pl/api/api-data'
PPK_NN_FUND_CODE = 'FZD2055'
PPK_DEFAULT_FUND_ID = '61777738'
_refresh_lock = RLock()
_failed_refreshes = {}
logger = logging.getLogger(__name__)

PPK_PRICE_URL = 'https://mojefundusze.pl/Fundusze/PPK/Nationale-Nederlanden-DFE-Nasze-Jutro-2055-PPK'
PPK_BIZNESRADAR_HISTORY_URL = 'https://www.biznesradar.pl/notowania-historyczne/NNDN55.TFI'

def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))

def _q(value: Decimal, places: str = '0.01') -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))

class PPKService:
    @staticmethod
    def get_cached_price(fund_id: str = '61777738') -> Optional[Dict[str, Any]]:
        cached = get_db().execute(
            'SELECT data FROM ppk_weekly_history WHERE fund_id = ?',
            (fund_id,),
        ).fetchone()
        if not cached:
            return None

        cached_data = json.loads(cached['data'])
        if not cached_data:
            return None

        eligible = PPKService._valid_points(cached_data, 'week')
        if not eligible:
            return None
        latest = max(eligible, key=lambda p: p['week'])
        result = {'price': latest['price'], 'date': latest['week']}
        if latest.get('source'):
            result['source'] = latest['source']
        return result

    @staticmethod
    def _valid_points(points, date_field='date') -> list[dict]:
        valid = {}
        for point in points:
            try:
                stamp = str(point[date_field])[:10]
                day = date.fromisoformat(stamp)
                price = float(point['price'])
                if day > date.today() or not math.isfinite(price) or price <= 0:
                    continue
                valid[stamp] = {date_field: stamp, 'price': price}
                if point.get('source'):
                    valid[stamp]['source'] = point['source']
            except (KeyError, TypeError, ValueError):
                continue
        return [valid[stamp] for stamp in sorted(valid)]

    @staticmethod
    def _fetch_nn_json(path: str):
        url = PPK_NN_API_URL + '?' + urlencode({'pathname': path})
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode('utf-8'))

    @staticmethod
    def _parse_nn_current(data) -> dict:
        rows = [item for item in data.get('items', [])
                if item.get('code') == PPK_NN_FUND_CODE and item.get('product') == 'PPK'
                and item.get('currency') == 'PLN']
        points = PPKService._valid_points([
            {'date': row.get('quoteDate'), 'price': row.get('purchasePrice'), 'source': 'Nationale-Nederlanden'}
            for row in rows
        ])
        if not points:
            raise ValueError('Brak poprawnej wyceny funduszu NN Nasze Jutro 2055.')
        return points[-1]

    @staticmethod
    def _parse_nn_history(data) -> list[dict]:
        graph = data.get(PPK_NN_FUND_CODE, {}).get('graphData', {})
        points = PPKService._valid_points([
            {'date': stamp, 'price': price, 'source': 'Nationale-Nederlanden'}
            for stamp, price in graph.items()
        ])
        if not points:
            raise ValueError('Brak poprawnej historii wycen funduszu NN Nasze Jutro 2055.')
        return points

    @staticmethod
    def refresh_price(portfolio_id: int, force: bool = False) -> dict:
        # Serialize requests so the list and detail view share one cache update.
        db = get_db()
        with _refresh_lock:
            cached = PPKService.get_cached_price()
            cache_row = db.execute('SELECT CAST(updated_at AS TEXT) AS updated_at FROM ppk_weekly_history WHERE fund_id=?',
                                   (PPK_DEFAULT_FUND_ID,)).fetchone()
            if not force and cached and cache_row:
                try:
                    checked = datetime.fromisoformat(cache_row['updated_at'])
                    if 0 <= (datetime.now(timezone.utc).replace(tzinfo=None) - checked).total_seconds() < 12 * 3600:
                        return {'currentPrice': cached, 'changed': False, 'warning': None}
                except (ValueError, TypeError):
                    pass
            cache_key = tuple(db.execute('PRAGMA database_list').fetchone()) + (PPK_DEFAULT_FUND_ID,)
            failed = _failed_refreshes.get(cache_key)
            if not force and failed and time.monotonic() - failed[0] < 600:
                return {'currentPrice': cached, 'changed': False, 'warning': failed[1]}
            first = db.execute("SELECT MIN(t.date) FROM ppk_transactions t JOIN portfolios p ON p.id=t.portfolio_id WHERE p.account_type='PPK'").fetchone()[0]
            result = PPKService.update_cache(PPK_DEFAULT_FUND_ID, first or date.today().isoformat())
            warning = result.get('warning')
            if warning:
                _failed_refreshes[cache_key] = (time.monotonic(), warning)
            else:
                _failed_refreshes.pop(cache_key, None)
            latest = PPKService.get_cached_price()
            return {'currentPrice': latest, 'changed': latest != cached, 'warning': warning}

    @staticmethod
    def _parse_biznesradar_history(html: str) -> list[dict]:
        rows = re.findall(
            r'(\d{2}\.\d{2}\.\d{4})\s*</td>\s*<td[^>]*>\s*([0-9]+(?:[.,][0-9]+)?)',
            html,
            re.IGNORECASE,
        )
        parsed: list[dict] = []
        for date_pl, price_raw in rows:
            day, month, year = date_pl.split('.')
            iso_date = f'{year}-{month}-{day}'
            parsed.append({
                'date': iso_date,
                'price': float(price_raw.replace(',', '.')),
            })
        return parsed

    @staticmethod
    def _iso_week_key(date_str: str) -> tuple:
        dt = date.fromisoformat(date_str)
        iso_year, iso_week, _ = dt.isocalendar()
        return (iso_year, iso_week)

    @staticmethod
    def fetch_current_price() -> Dict[str, Any]:
        try:
            return PPKService._parse_nn_current(PPKService._fetch_nn_json(
                '/funds/pension/overview?' + urlencode({'quoteDate': date.today().isoformat(), 'size': 200, 'sort': 'name,asc'})
            ))
        except Exception as exc:
            logger.warning('Official NN PPK quote unavailable: %s', exc)
        try:
            request = Request(PPK_BIZNESRADAR_HISTORY_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(request, timeout=8) as response:
                points = PPKService._valid_points(PPKService._parse_biznesradar_history(response.read().decode('utf-8', 'ignore')))
            if points:
                return dict(points[-1], source='BiznesRadar')
        except Exception as exc:
            logger.warning('Alternative PPK quote unavailable: %s', exc)
        request = Request(
            PPK_PRICE_URL,
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'text/html',
            },
        )

        with urlopen(request, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')

        # Primary pattern for current mojefundusze layout.
        date_match = re.search(r'Wycena\s+z\s+dnia\s+(\d{4}-\d{2}-\d{2})', html, re.IGNORECASE)
        price_match = re.search(r'class=["\']fund-price["\']>\s*([0-9\s,\.]+)\s*<span[^>]*>\s*PLN', html, re.IGNORECASE)

        # Fallbacks for older HTML variants.
        if not date_match:
            date_match = re.search(r'class=["\']info-value["\']>\s*(\d{4}-\d{2}-\d{2})\s*<', html, re.IGNORECASE)
        if not date_match:
            date_match = re.search(r'<strong>\s*(\d{4}-\d{2}-\d{2})\s*</strong>', html, re.IGNORECASE)

        if not price_match:
            price_match = re.search(r'<h1>\s*([0-9\s,\.]+)\s*PLN\s*</h1>', html, re.IGNORECASE)
        if not price_match:
            price_match = re.search(r'Wycena:\s*([0-9\s,\.]+)\s*PLN', html, re.IGNORECASE)

        if not date_match or not price_match:
            raise ValueError('Nie udało się pobrać aktualnej ceny PPK ze strony źródłowej.')

        price = float(price_match.group(1).replace(' ', '').replace(',', '.'))
        points = PPKService._valid_points([{'date': date_match.group(1), 'price': price}])
        if not points:
            raise ValueError('Niepoprawna cena lub data wyceny PPK.')
        return {
            'price': _q(Decimal(str(price))),
            'date': date_match.group(1),
            'source': 'mojeFundusze',
        }

    @staticmethod
    def fetch_daily_history(fund_id: str) -> list[dict]:
        if fund_id != PPK_DEFAULT_FUND_ID:
            raise ValueError('Nieobsługiwany fundusz PPK. Skonfigurowany jest NN Nasze Jutro 2055.')
        try:
            return PPKService._parse_nn_history(PPKService._fetch_nn_json(
                '/funds/quotes/graph?' + urlencode({'codes': PPK_NN_FUND_CODE, 'from': '2019-09-09', 'to': date.today().isoformat()})
            ))
        except Exception as exc:
            logger.warning('Official NN PPK history unavailable: %s', exc)
        history_by_date: dict[str, float] = {}

        # Primary source: BiznesRadar historical table (supports pagination via ",<page>").
        try:
            for page in range(1, 40):
                page_url = PPK_BIZNESRADAR_HISTORY_URL if page == 1 else f'{PPK_BIZNESRADAR_HISTORY_URL},{page}'
                request = Request(
                    page_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'text/html',
                    },
                )
                with urlopen(request, timeout=10) as response:
                    html = response.read().decode('utf-8', errors='ignore')
                    parsed_page = PPKService._parse_biznesradar_history(html)
                    if not parsed_page:
                        break
                    for entry in parsed_page:
                        history_by_date[entry['date']] = entry['price']
        except Exception as e:
            print(f"Error fetching BiznesRadar daily history: {e}")

        if history_by_date:
            history = [{'date': dt, 'price': price} for dt, price in history_by_date.items()]
            history.sort(key=lambda x: x['date'])
            return [dict(point, source='BiznesRadar') for point in PPKService._valid_points(history)]

        # Fallback source: mojefundusze JSON endpoint.
        url = f'https://mojefundusze.pl/inc/wykres_small.php?ID={fund_id}&OK=9'
        request = Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                raw_data = response.read().decode('utf-8', errors='ignore')
                parsed = json.loads(raw_data)
                if 'series' not in parsed or not parsed['series']:
                    return []
                data_points = parsed['series'][0].get('data', [])
                history = []
                for point in data_points:
                    if len(point) == 2:
                        history.append({'date': point[0], 'price': float(point[1])})
                history.sort(key=lambda x: x['date'])
                return [dict(point, source='mojeFundusze') for point in PPKService._valid_points(history)]
        except Exception as e:
            print(f"Error fetching daily history for {fund_id}: {e}")
            return []

    @staticmethod
    def aggregate_weekly(daily_data: list[dict]) -> list[dict]:
        # Preserve the actual quotation date; gaps must not pretend to be fresh quotes.
        weeks = {}
        for point in PPKService._valid_points(daily_data):
            key = PPKService._iso_week_key(point['date'])
            weeks[key] = dict(point)
        return [dict({'week': point['date'], 'price': point['price']},
                     **({'source': point['source']} if point.get('source') else {}))
                for point in sorted(weeks.values(), key=lambda point: point['date'])]

    @staticmethod
    def update_cache(fund_id: str, first_contribution_date: str, cached_only: bool = False) -> dict:
        db = get_db()
        cached = db.execute('SELECT data, last_week FROM ppk_weekly_history WHERE fund_id=?', (fund_id,)).fetchone()
        cached_data = PPKService._valid_points(json.loads(cached['data']), 'week') if cached else []
        if cached_only:
            return {'data': cached_data, 'last_week': cached_data[-1]['week'] if cached_data else None,
                    'latest_price': cached_data[-1]['price'] if cached_data else None}
        daily = PPKService._valid_points(PPKService.fetch_daily_history(fund_id))
        if not daily:
            try:
                daily = [PPKService.fetch_current_price()]
            except Exception as exc:
                logger.warning('PPK refresh failed: %s', exc)
        warning = None
        if not daily:
            warning = 'Nie udało się pobrać wyceny PPK. Zachowano ostatnią zapisaną cenę.'
        elif cached_data and daily[-1]['date'] < cached_data[-1]['week']:
            warning = 'Źródło zwróciło starszą wycenę PPK. Zachowano nowszą zapisaną cenę.'
        else:
            # Replace the current ISO week when a newer day arrives instead of dropping it.
            by_week = {PPKService._iso_week_key(p['week']): p for p in cached_data}
            filtered = [p for p in daily if p['date'] >= first_contribution_date]
            for point in PPKService.aggregate_weekly(filtered or daily[-1:]):
                key = PPKService._iso_week_key(point['week'])
                existing = by_week.get(key)
                if not existing or point['week'] >= existing['week']:
                    by_week[key] = point
            cached_data = sorted(by_week.values(), key=lambda point: point['week'])
            if cached_data:
                db.execute("""INSERT INTO ppk_weekly_history(fund_id,data,last_week,updated_at)
                    VALUES (?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(fund_id) DO UPDATE SET
                    data=excluded.data,last_week=excluded.last_week,updated_at=CURRENT_TIMESTAMP""",
                    (fund_id, json.dumps(cached_data), cached_data[-1]['week']))
                db.commit()
        return {'data': cached_data, 'last_week': cached_data[-1]['week'] if cached_data else None,
                'latest_price': cached_data[-1]['price'] if cached_data else None, 'warning': warning}

    @staticmethod
    def compute_performance(portfolio_id: int, fund_id: str, cached_only: bool = False) -> dict:
        db = get_db()
        first_tx = db.execute(
            'SELECT date FROM ppk_transactions WHERE portfolio_id = ? ORDER BY date ASC LIMIT 1',
            (portfolio_id,)
        ).fetchone()
        
        if not first_tx:
            return {
                'start_week': None,
                'start_price': 0,
                'current_price': 0,
                'return_pln': 0,
                'return_pct': 0,
                'chart': []
            }
            
        first_date = first_tx['date']
        
        # Incremental update
        cache_result = PPKService.update_cache(fund_id, first_date, cached_only=cached_only)
        weekly_data = [p for p in cache_result['data'] if p['week'] <= date.today().isoformat() and float(p['price']) > 0]
        current_price = weekly_data[-1]['price'] if weekly_data else None
        
        if not weekly_data:
             return {
                'start_week': None,
                'start_price': 0,
                'current_price': current_price,
                'return_pln': None,
                'return_pct': None,
                'valuation_status': 'incomplete',
                'chart': []
            }

        start_week_entry = weekly_data[0]
        start_price = start_week_entry['price']
        
        # Portfolio value history
        transactions = db.execute(
            'SELECT date, employee_units, employer_units, price_per_unit FROM ppk_transactions WHERE portfolio_id = ? ORDER BY date ASC',
            (portfolio_id,)
        ).fetchall()
        
        tx_list = [dict(tx) for tx in transactions]
        
        extended_chart = []
        for week_point in weekly_data:
            week_date = week_point['week']
            week_price = week_point['price']
            
            # Filter transactions up to this week
            tx_up_to_week = [tx for tx in tx_list if tx['date'] <= week_date]
            
            if tx_up_to_week:
                # Use calculate_metrics to get all values including tax-adjusted ones
                week_metrics = PPKCalculation.calculate_metrics(tx_up_to_week, Decimal(str(week_price)))
                
                extended_chart.append({
                    'week': week_date,
                    'price': week_price,
                    'value': week_metrics['totalCurrentValue'],
                    'net_value': week_metrics['totalNetValue'],
                    'net_contributions': week_metrics['totalPurchaseValue']
                })
            else:
                extended_chart.append({
                    'week': week_date,
                    'price': week_price,
                    'value': 0,
                    'net_value': 0,
                    'net_contributions': 0
                })
            
        summary = PPKService.get_portfolio_summary(portfolio_id, current_price)
        
        return {
            'start_week': start_week_entry['week'],
            'start_price': start_price,
            'current_price': current_price,
            'return_pln': summary['totalProfit'],
            'return_pct': summary['totalProfit'] / summary['totalPurchaseValue'] * 100 if summary['totalPurchaseValue'] > 0 else None,
            'valuation_status': quote_status(current_price, weekly_data[-1]['week']),
            'valuation_as_of': weekly_data[-1]['week'],
            'chart': extended_chart
        }

    @staticmethod
    def get_transactions(portfolio_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            '''SELECT id, portfolio_id, date, employee_units, employer_units, price_per_unit
               FROM ppk_transactions
               WHERE portfolio_id = ?
               ORDER BY date DESC, id DESC''',
            (portfolio_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def add_transaction(portfolio_id: int, tx_date: str, employee_units: float, employer_units: float, price_per_unit: float) -> bool:
        db = get_db()
        if not tx_date:
            tx_date = date.today().isoformat()

        db.execute(
            '''INSERT INTO ppk_transactions
               (portfolio_id, date, employee_units, employer_units, price_per_unit)
               VALUES (?, ?, ?, ?, ?)''',
            (portfolio_id, tx_date, employee_units, employer_units, price_per_unit)
        )
        db.commit()
        return True

    @staticmethod
    def get_portfolio_summary(portfolio_id: int, current_price: Optional[float] = None) -> PPKSummaryDTO:
        transactions = PPKService.get_transactions(portfolio_id)
        
        c_price_decimal = Decimal(str(current_price)) if current_price is not None else None
        
        return PPKCalculation.calculate_metrics(transactions, c_price_decimal)

    @staticmethod
    def create_portfolio_entry(portfolio_id: int, name: str, created_at: str) -> None:
        db = get_db()
        db.execute(
            '''INSERT INTO ppk_portfolios (id, name, created_at)
               VALUES (?, ?, ?)''',
            (portfolio_id, name, created_at)
        )
        db.commit()

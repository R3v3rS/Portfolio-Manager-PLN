from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import re
import json
from urllib.request import Request, urlopen
from typing import Optional, Dict, Any

from database import get_db
from .ppk_calculation import PPKCalculation
from .ppk_dto import PPKSummaryDTO

PPK_PRICE_URL = 'https://mojefundusze.pl/Fundusze/PPK/Nationale-Nederlanden-DFE-Nasze-Jutro-2055-PPK'
PPK_BIZNESRADAR_HISTORY_URL = 'https://www.biznesradar.pl/notowania-historyczne/NNDN55.TFI'

def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))

def _q(value: Decimal, places: str = '0.01') -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))

class PPKService:
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
        return {
            'price': _q(Decimal(str(price))),
            'date': date_match.group(1),
        }

    @staticmethod
    def fetch_daily_history(fund_id: str) -> list[dict]:
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
            return history

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
                return history
        except Exception as e:
            print(f"Error fetching daily history for {fund_id}: {e}")
            return []

    @staticmethod
    def aggregate_weekly(daily_data: list[dict]) -> list[dict]:
        if not daily_data:
            return []

        # Group by calendar week
        weeks_map = {}
        min_date = date.fromisoformat(daily_data[0]['date'])
        max_date = date.fromisoformat(daily_data[-1]['date'])
        
        for entry in daily_data:
            dt = date.fromisoformat(entry['date'])
            iso_year, iso_week, _ = dt.isocalendar()
            key = (iso_year, iso_week)
            
            if key not in weeks_map:
                weeks_map[key] = entry
            else:
                if entry['date'] > weeks_map[key]['date']:
                    weeks_map[key] = entry

        weekly_history = []
        current_dt = min_date
        # Move to the Monday of the starting week to ensure consistent iteration
        current_dt = current_dt - timedelta(days=current_dt.weekday())
        
        last_known_price = daily_data[0]['price']
        
        while current_dt <= max_date:
            iso_year, iso_week, _ = current_dt.isocalendar()
            key = (iso_year, iso_week)
            
            if key in weeks_map:
                last_known_price = weeks_map[key]['price']
                ref_date = weeks_map[key]['date']
            else:
                # No data for this week, use last known price
                # Friday of the week as fallback reference date
                friday_of_week = current_dt + timedelta(days=4)
                ref_date = min(friday_of_week, max_date).isoformat()
            
            weekly_history.append({
                'week': ref_date,
                'price': last_known_price
            })
            
            current_dt += timedelta(days=7)
            
        return weekly_history

    @staticmethod
    def update_cache(fund_id: str, first_contribution_date: str) -> dict:
        db = get_db()
        cached = db.execute(
            'SELECT data, last_week FROM ppk_weekly_history WHERE fund_id = ?',
            (fund_id,)
        ).fetchone()

        daily_history = PPKService.fetch_daily_history(fund_id)
        latest_price = daily_history[-1]['price'] if daily_history else 0
        
        if not daily_history:
            if cached:
                return {
                    'data': json.loads(cached['data']),
                    'last_week': cached['last_week'],
                    'latest_price': 0
                }
            return {'data': [], 'last_week': None, 'latest_price': 0}

        if cached:
            cached_data = json.loads(cached['data'])
            last_week = cached['last_week']
            
            # Compute only weeks AFTER last_week
            new_daily = [d for d in daily_history if d['date'] > last_week]
            if new_daily:
                new_weekly = PPKService.aggregate_weekly(new_daily)
                
                # Filter out duplicates (by ISO week) and append
                existing_weeks = {PPKService._iso_week_key(w['week']) for w in cached_data}
                filtered_new_weekly = [w for w in new_weekly if PPKService._iso_week_key(w['week']) not in existing_weeks]
                
                if filtered_new_weekly:
                    cached_data.extend(filtered_new_weekly)
                    last_week = cached_data[-1]['week']
                    
                    db.execute(
                        'UPDATE ppk_weekly_history SET data = ?, last_week = ?, updated_at = CURRENT_TIMESTAMP WHERE fund_id = ?',
                        (json.dumps(cached_data), last_week, fund_id)
                    )
                    db.commit()
            
            return {'data': cached_data, 'last_week': last_week, 'latest_price': latest_price}
        else:
            # Full compute from first_contribution_date
            filtered_daily = [d for d in daily_history if d['date'] >= first_contribution_date]
            if not filtered_daily and daily_history:
                filtered_daily = [daily_history[-1]] # At least something
                
            weekly_data = PPKService.aggregate_weekly(filtered_daily)
            if weekly_data:
                last_week = weekly_data[-1]['week']
                db.execute(
                    'INSERT INTO ppk_weekly_history (fund_id, data, last_week) VALUES (?, ?, ?)',
                    (fund_id, json.dumps(weekly_data), last_week)
                )
                db.commit()
                return {'data': weekly_data, 'last_week': last_week, 'latest_price': latest_price}
            
            return {'data': [], 'last_week': None, 'latest_price': latest_price}

    @staticmethod
    def compute_performance(portfolio_id: int, fund_id: str) -> dict:
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
        cache_result = PPKService.update_cache(fund_id, first_date)
        weekly_data = cache_result['data']
        current_price = cache_result['latest_price']
        
        if not weekly_data:
             return {
                'start_week': None,
                'start_price': 0,
                'current_price': current_price,
                'return_pln': 0,
                'return_pct': 0,
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
            'return_pln': float(summary['netProfit']),
            'return_pct': float(summary['netProfit'] / summary['totalPurchaseValue'] * 100) if summary['totalPurchaseValue'] > 0 else 0,
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

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.exceptions import NotFoundError, ValidationError
from database import get_db


class CategoryService:
    @staticmethod
    def get_all(category_type: str):
        normalized_type = (category_type or '').strip().upper()
        if normalized_type not in ('SECTOR', 'COUNTRY'):
            raise ValidationError('Invalid category type', details={'type': category_type})

        db = get_db()
        rows = db.execute(
            '''SELECT id, type, name FROM categories WHERE type = ? ORDER BY name ASC''',
            (normalized_type,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def resolve(name: str, category_type: str) -> int:
        cleaned = (name or '').strip()
        normalized_type = (category_type or '').strip().upper()
        if not cleaned:
            raise ValidationError('Category name is required', details={'type': category_type})
        if normalized_type not in ('SECTOR', 'COUNTRY'):
            raise ValidationError('Invalid category type', details={'type': category_type})

        db = get_db()
        exact = db.execute(
            'SELECT id FROM categories WHERE type = ? AND lower(name) = lower(?)',
            (normalized_type, cleaned),
        ).fetchone()
        if exact:
            return int(exact['id'])

        alias = db.execute(
            '''SELECT category_id FROM category_aliases
               WHERE type = ? AND lower(alias) = lower(?)''',
            (normalized_type, cleaned),
        ).fetchone()
        if alias:
            return int(alias['category_id'])

        fuzzy = db.execute(
            '''SELECT id FROM categories
               WHERE type = ? AND (lower(name) LIKE lower(?) OR lower(?) LIKE '%' || lower(name) || '%')
               ORDER BY length(name) ASC LIMIT 1''',
            (normalized_type, f'%{cleaned}%', cleaned),
        ).fetchone()
        if fuzzy:
            return int(fuzzy['id'])

        cur = db.execute('INSERT INTO categories (type, name) VALUES (?, ?)', (normalized_type, cleaned))
        db.commit()
        return int(cur.lastrowid)


class InstrumentProfileService:
    @staticmethod
    def list_profiles():
        db = get_db()
        rows = db.execute(
            '''SELECT ip.ticker, ip.instrument_type, ip.sector_id, s.name AS sector_name,
                      ip.country_id, c.name AS country_name, ip.source, ip.status, ip.updated_at
               FROM instrument_profiles ip
               LEFT JOIN categories s ON s.id = ip.sector_id
               LEFT JOIN categories c ON c.id = ip.country_id
               ORDER BY ip.ticker ASC'''
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_profile(ticker: str):
        db = get_db()
        row = db.execute(
            '''SELECT ip.ticker, ip.instrument_type, ip.sector_id, s.name AS sector_name,
                      ip.country_id, c.name AS country_name, ip.source, ip.status, ip.updated_at
               FROM instrument_profiles ip
               LEFT JOIN categories s ON s.id = ip.sector_id
               LEFT JOIN categories c ON c.id = ip.country_id
               WHERE ip.ticker = ?''',
            ((ticker or '').strip().upper(),),
        ).fetchone()
        if not row:
            raise NotFoundError('Instrument profile not found', details={'ticker': ticker})
        return dict(row)

    @staticmethod
    def create_or_update_profile(data: dict[str, Any]):
        ticker = (data.get('ticker') or '').strip().upper()
        instrument_type = (data.get('instrument_type') or '').strip().upper()
        source = (data.get('source') or 'manual').strip().lower()
        status = (data.get('status') or 'verified').strip().lower()

        if not ticker:
            raise ValidationError('ticker is required')
        if instrument_type not in ('STOCK', 'ETF'):
            raise ValidationError('instrument_type must be STOCK or ETF')

        sector_id = CategoryService.resolve(data.get('sector_name') or '', 'SECTOR') if data.get('sector_name') else data.get('sector_id')
        country_id = CategoryService.resolve(data.get('country_name') or '', 'COUNTRY') if data.get('country_name') else data.get('country_id')

        db = get_db()
        db.execute(
            '''INSERT INTO instrument_profiles (ticker, instrument_type, sector_id, country_id, source, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET
                 instrument_type = excluded.instrument_type,
                 sector_id = excluded.sector_id,
                 country_id = excluded.country_id,
                 source = excluded.source,
                 status = excluded.status,
                 updated_at = excluded.updated_at''',
            (ticker, instrument_type, sector_id, country_id, source, status, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
        return InstrumentProfileService.get_profile(ticker)

    @staticmethod
    def set_status(ticker: str, status: str):
        db = get_db()
        db.execute(
            'UPDATE instrument_profiles SET status = ?, updated_at = ? WHERE ticker = ?',
            ((status or '').strip().lower(), datetime.now(timezone.utc).isoformat(), (ticker or '').strip().upper()),
        )
        db.commit()


class EtfAllocationService:
    @staticmethod
    def get_allocations(ticker: str):
        db = get_db()
        rows = db.execute(
            '''SELECT ea.id, ea.ticker, ea.category_id, c.name AS category_name, ea.type, ea.weight, ea.updated_at
               FROM etf_allocations ea
               LEFT JOIN categories c ON c.id = ea.category_id
               WHERE ea.ticker = ?
               ORDER BY ea.type, ea.weight DESC''',
            ((ticker or '').strip().upper(),),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def replace_allocations(ticker: str, data: list[dict[str, Any]]):
        normalized_ticker = (ticker or '').strip().upper()
        if not normalized_ticker:
            raise ValidationError('ticker is required')

        total = sum(float(item.get('weight', 0) or 0) for item in data)
        if total < 99 or total > 101:
            raise ValidationError('ETF allocation weights must sum approximately 100', details={'sum': total})

        db = get_db()
        db.execute('DELETE FROM etf_allocations WHERE ticker = ?', (normalized_ticker,))
        now = datetime.now(timezone.utc).isoformat()
        for item in data:
            category_id = item.get('category_id')
            if not category_id and item.get('category_name') and item.get('type'):
                category_id = CategoryService.resolve(item['category_name'], item['type'])
            db.execute(
                '''INSERT INTO etf_allocations (ticker, category_id, type, weight, updated_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (normalized_ticker, category_id, (item.get('type') or '').upper(), float(item.get('weight', 0) or 0), now),
            )
        db.commit()
        return EtfAllocationService.get_allocations(normalized_ticker)


class AiClassificationService:
    @staticmethod
    def classify_instrument(ticker: str, name: str, description: str):
        sectors = CategoryService.get_all('SECTOR')
        countries = CategoryService.get_all('COUNTRY')
        return {
            'ticker': (ticker or '').strip().upper(),
            'suggested_instrument_type': 'ETF' if 'etf' in (name or '').lower() else 'STOCK',
            'suggested_sector': sectors[0]['name'] if sectors else 'Other',
            'suggested_country': countries[0]['name'] if countries else 'Other',
            'confidence': 0.45,
            'source': 'ai',
            'status': 'ai',
            'note': f'Mock suggestion from AI for {name}. Not persisted.',
            'context': {'description': description},
        }

    @staticmethod
    def classify_etf(text: str):
        return {
            'source': 'ai',
            'status': 'ai',
            'allocations': [
                {'type': 'SECTOR', 'category_name': 'Information Technology', 'weight': 30.0},
                {'type': 'SECTOR', 'category_name': 'Financials', 'weight': 20.0},
                {'type': 'COUNTRY', 'category_name': 'United States', 'weight': 60.0},
                {'type': 'COUNTRY', 'category_name': 'Other', 'weight': 40.0},
            ],
            'raw_text': text,
        }

"""User reference prices are separate from market history and financial transactions."""
import math
import re
from datetime import date, datetime
from database import get_db
from api.exceptions import ApiError, ValidationError


def init_manual_price_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS manual_stock_prices (
        ticker TEXT PRIMARY KEY, price REAL NOT NULL CHECK(price>0),
        price_date TEXT NOT NULL, currency TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL
    )''')


def records(tickers):
    if not tickers:
        return {}
    marks=','.join('?' for _ in tickers)
    return {r['ticker']:dict(r) for r in get_db().execute(
        f'SELECT * FROM manual_stock_prices WHERE ticker IN ({marks})',tickers)}


def save(ticker,payload,clear=False):
    ticker=str(ticker).strip().upper()
    if not re.fullmatch(r'[A-Z0-9.^=_-]{1,40}',ticker):
        raise ValidationError('Niepoprawny symbol instrumentu.')
    version=payload.get('version',0)
    if type(version) is not int or version<0:
        raise ValidationError('Niepoprawna wersja ceny.')
    price=None
    stamp=payload.get('date')
    if not clear:
        raw=payload.get('price')
        if isinstance(raw,bool):raise ValidationError('Podaj dodatnią cenę jednostkową.')
        try:
            price=float(raw)
            if not math.isfinite(price) or not 0<price<=1e9:raise ValueError()
            parsed=date.fromisoformat(stamp)
            if parsed.isoformat()!=stamp or parsed>date.today():raise ValueError()
        except (ValueError,TypeError):
            raise ValidationError('Podaj dodatnią cenę i poprawną datę nie późniejszą niż dziś.') from None
    db=get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        held=db.execute('SELECT DISTINCT COALESCE(currency,\'PLN\') AS currency FROM holdings WHERE ticker=? AND quantity>0',(ticker,)).fetchall()
        if len(held)!=1:raise ValidationError('Cena ręczna wymaga posiadanej pozycji z jednoznaczną walutą.')
        current=db.execute('SELECT * FROM manual_stock_prices WHERE ticker=?',(ticker,)).fetchone()
        if (current['version'] if current else 0)!=version:
            raise ApiError('manual_price_conflict','Cena zmieniła się. Odśwież pozycje i spróbuj ponownie.',status=409)
        if clear:
            if current:db.execute('UPDATE manual_stock_prices SET active=0,version=version+1,updated_at=? WHERE ticker=?',(datetime.now().isoformat(),ticker))
        else:
            db.execute('''INSERT INTO manual_stock_prices(ticker,price,price_date,currency,version,updated_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(ticker) DO UPDATE SET price=excluded.price,
                price_date=excluded.price_date,currency=excluded.currency,active=1,version=excluded.version,updated_at=excluded.updated_at''',
                (ticker,price,stamp,held[0]['currency'].upper(),version+1,datetime.now().isoformat()))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'ticker':ticker,'active':not clear,'version':version+1 if current or not clear else 0}

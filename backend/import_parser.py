"""Parse XTB cash-operation exports without changing portfolio balances."""

import pandas as pd
import math
from numbers import Real

from portfolio_import_service import PortfolioImportService as Helpers


TYPE_MAP = {
    'deposit': 'DEPOSIT', 'ike deposit': 'DEPOSIT', 'withdrawal': 'WITHDRAW',
    'free funds interest': 'INTEREST', 'stock purchase': 'BUY', 'stock sell': 'SELL',
    'dividend': 'DIVIDEND',
}


def operation_id(value):
    if pd.isna(value):
        return None
    if isinstance(value, Real):
        if isinstance(value, bool) or not math.isfinite(value) or value != int(value) or abs(value) > 2**53:
            raise ValueError('Niepoprawny lub nieprecyzyjny identyfikator operacji. Wyeksportuj ID jako tekst.')
        return str(int(value))
    return str(value).strip() or None


def parse_xtb_dataframe(df, normalize_date):
    columns = {str(col).strip().lower(): col for col in df.columns}
    select = lambda aliases: Helpers._select_column(columns, aliases)
    time_col = select(['time', 'date', 'close time'])
    type_col = select(['type', 'transaction type'])
    amount_col = Helpers._select_column(columns, ['amount', 'profit', 'p/l', 'profit/loss', 'result'],
                                        df=df, numeric_preferred=True)
    missing = [name for name, col in [('Time', time_col), ('Type', type_col), ('Amount', amount_col)] if col is None]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    comment_col = select(['comment', 'description', 'details'])
    symbol_col = select(['ticker', 'symbol', 'instrument'])
    instrument_col = select(['instrument'])
    id_col = select(['id', 'operation id', 'transaction id'])
    commission_col = select(['commission', 'fee', 'fees', 'prowizja'])
    currency_col = select(['account currency', 'currency'])
    parsed, unsupported, mappings = [], [], {}
    source_rows = df.attrs.get('source_rows', range(1, len(df) + 1))
    for position, (_, row) in enumerate(df.iterrows(), start=1):
        number = source_rows[position - 1]
        raw_type = str(row[type_col]).strip()
        tx_type = TYPE_MAP.get(raw_type.lower())
        if tx_type is None:
            unsupported.append({'row_number': number, 'type': raw_type,
                                'reason': 'Nieobsługiwany rodzaj operacji — nie został zaksięgowany.'})
            continue
        if currency_col is not None and not pd.isna(row[currency_col]):
            if str(row[currency_col]).strip().upper() != 'PLN':
                raise ValueError(f'Wiersz {number}: import wymaga kwot rachunku w PLN.')
        amount = Helpers._try_parse_float(row[amount_col])
        if amount is None or amount == 0:
            raise ValueError(f"Invalid numeric value in column '{amount_col}' at row {number}: {row[amount_col]}")
        amount = abs(amount)
        date = normalize_date(row[time_col], number)
        comment = '' if comment_col is None or pd.isna(row[comment_col]) else str(row[comment_col])
        qty = Helpers._parse_xtb_quantity(comment, number) if tx_type in {'BUY', 'SELL'} else 1.0
        symbol = '' if symbol_col is None or pd.isna(row[symbol_col]) else str(row[symbol_col]).strip()
        mapping = None
        if symbol and tx_type in {'BUY', 'SELL', 'DIVIDEND'}:
            if symbol not in mappings:
                mappings[symbol] = Helpers.resolve_import_symbol(symbol)
            mapping = mappings[symbol]
        missing_symbol = tx_type in {'BUY', 'SELL'} or (tx_type == 'DIVIDEND' and bool(symbol))
        missing_symbol = missing_symbol and mapping is None
        ticker = mapping.ticker if mapping else ((symbol.upper() or 'UNKNOWN') if missing_symbol else 'CASH')
        commission = None
        if commission_col is not None and not pd.isna(row[commission_col]):
            commission = Helpers._try_parse_float(row[commission_col])
            if commission is None:
                raise ValueError(f'Wiersz {number}: niepoprawna prowizja.')
            commission = abs(commission)
        gross = amount
        if tx_type == 'BUY':
            gross -= commission or 0
        elif tx_type == 'SELL':
            gross += commission or 0
        if gross <= 0:
            raise ValueError(f'Wiersz {number}: prowizja jest większa od wartości zakupu.')
        parsed.append({
            'ticker': ticker, 'type': tx_type, 'quantity': qty, 'total_value': amount,
            'price': gross / qty, 'date': date, 'symbol_input': symbol,
            'commission': commission if tx_type in {'BUY', 'SELL'} else None,
            'status': 'rejected' if missing_symbol else 'pending',
            'conflict_type': 'missing_symbol' if missing_symbol else None,
            'conflict_details': {'symbol_input': symbol} if missing_symbol else None,
            'row_hash': Helpers._generate_row_hash(date, ticker, amount, tx_type, qty),
            'source_account': df.attrs.get('source_account'),
            'source_operation_id': None if id_col is None else operation_id(row[id_col]),
            'source_row_number': number,
            'instrument_name': None if instrument_col is None or pd.isna(row[instrument_col]) else str(row[instrument_col]).strip(),
        })
    parsed.sort(key=lambda row: pd.Timestamp(row['date']))
    warnings = []
    if df.attrs.get('cash_operations_xlsx'):
        warnings.append('Odczytano wyłącznie Cash Operations. Kwoty są przepływami rachunku w PLN; czas zachowano zgodnie z eksportem (UTC).')
    if id_col is not None and not df.attrs.get('source_account'):
        warnings.append('Brak numeru rachunku w pliku. Duplikaty sprawdzamy po danych transakcji, bez identyfikatora rachunku brokera.')
    if any(row['type'] in {'BUY', 'SELL'} and row['commission'] is None for row in parsed):
        warnings.append('Brak kwoty prowizji dla części transakcji. Amount traktujemy jako końcowy przepływ w PLN; opłat nie doliczamy drugi raz. Prowizji nie da się osobno ustalić z tego pliku.')
    return parsed, unsupported, warnings

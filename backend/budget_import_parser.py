"""Strict, locale-aware CSV and conservative receipt text parsing."""
import csv
import hashlib
import io
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from api.exceptions import ValidationError

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_ROWS = 3000


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold().replace('ł', 'l'))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', value)).strip()


def number(value, signed=True):
    raw = str(value or '').strip().replace('\u2212', '-').replace('\xa0', '').replace(' ', '')
    raw = re.sub(r'(?i)(PLN|zł)$', '', raw).strip()
    if raw.startswith('(') and raw.endswith(')'):
        raw = '-' + raw[1:-1]
    if ',' in raw and '.' in raw:
        if raw.rfind(',') > raw.rfind('.'):
            raw = raw.replace('.', '').replace(',', '.')
        else:
            raw = raw.replace(',', '')
    else:
        raw = raw.replace(',', '.')
    if not re.fullmatch(r'[+-]?\d+(?:\.\d{1,2})?', raw):
        raise ValidationError('Nieprawidłowa kwota; wymagane złote i najwyżej dwa miejsca po przecinku.')
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or abs(amount) > Decimal('999999999.99') or (not signed and amount <= 0):
            raise InvalidOperation
        return int(amount * 100)
    except InvalidOperation:
        raise ValidationError('Kwota jest poza dopuszczalnym zakresem.') from None


def parsed_date(value):
    raw = str(value or '').strip()[:10]
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y', '%Y.%m.%d'):
        try:
            result = datetime.strptime(raw, fmt).date()
            if not date(2000, 1, 1) <= result <= date.today():
                raise ValidationError('Data operacji musi być od roku 2000 do dzisiaj.')
            return result.isoformat()
        except ValueError:
            pass
    raise ValidationError('Nie rozpoznano daty operacji.')


def read_csv(content, header_index=None):
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValidationError('Wybierz niepusty CSV do 8 MB.')
    encoding = 'utf-16' if content.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    try:
        text = content.decode(encoding)
    except UnicodeDecodeError:
        encoding = 'cp1250'
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            raise ValidationError('Zapisz plik CSV w kodowaniu UTF-8 lub Windows-1250.') from None
    if not text.strip():
        raise ValidationError('Plik CSV nie zawiera operacji.')
    sample = text[:20000]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=';,\t').delimiter
    except csv.Error:
        delimiter = max(';\t,', key=lambda d: sample.splitlines()[0].count(d))
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter, strict=True))
    except csv.Error:
        raise ValidationError('Plik ma nieprawidłowy układ CSV.') from None
    if len(rows) > MAX_ROWS + 30:
        raise ValidationError(f'Jeden import może zawierać najwyżej {MAX_ROWS} operacji.')
    if header_index is None:
        candidates = [(i, row) for i, row in enumerate(rows[:20]) if len(row) >= 2]
        if not candidates:
            raise ValidationError('Nie znaleziono kolumn CSV.')
        recognizable = [(i, row) for i, row in candidates if any('data' in normalized(c) or normalized(c) == 'date' for c in row)]
        header_index = (recognizable or sorted(candidates, key=lambda item: -len(item[1])))[0][0]
    if type(header_index) is not int or not 0 <= header_index < min(20, len(rows)):
        raise ValidationError('Nieprawidłowy wiersz nagłówków.')
    headers = [c.strip()[:150] or f'Kolumna {i+1}' for i, c in enumerate(rows[header_index])]
    if not 2 <= len(headers) <= 80:
        raise ValidationError('CSV musi zawierać od 2 do 80 kolumn.')
    data = [r for r in rows[header_index+1:] if any(c.strip() for c in r)]
    if not data or len(data) > MAX_ROWS:
        raise ValidationError(f'Wybierz plik zawierający od 1 do {MAX_ROWS} operacji.')
    signature = hashlib.sha256('|'.join(normalized(c) for c in headers).encode()).hexdigest()
    return dict(headers=headers, rows=data, header_index=header_index, encoding=encoding,
                delimiter=delimiter, signature=signature)


ALIASES = {
    'date': ('data ksiegowania', 'booking date', 'data operacji', 'data transakcji', 'data', 'date'),
    'amount': ('kwota transakcji', 'kwota operacji', 'kwota', 'amount', 'wartosc'),
    'description': ('opis operacji', 'tytul operacji', 'tytul', 'opis', 'description', 'szczegoly'),
    'merchant': ('nazwa kontrahenta', 'nadawca odbiorca', 'nazwa odbiorcy', 'odbiorca', 'kontrahent', 'merchant', 'recipient'),
    'currency': ('waluta', 'currency'),
    'reference': ('identyfikator transakcji', 'id transakcji', 'identyfikator operacji', 'transaction id', 'id', 'reference'),
    'debit': ('obciazenie', 'wydatki', 'debit'),
    'credit': ('uznanie', 'wplywy', 'credit'),
}


def guessed_mapping(headers):
    names = [normalized(h) for h in headers]
    result = {}
    for key, aliases in ALIASES.items():
        index = next((names.index(alias) for alias in aliases if alias in names), None)
        result[key] = str(index) if index is not None else ''
    return result


def validate_mapping(mapping, width):
    if not isinstance(mapping, dict) or set(mapping) - set(ALIASES):
        raise ValidationError('Nieprawidłowe mapowanie kolumn.')
    result = {}
    for key in ALIASES:
        value = mapping.get(key, '')
        if value in ('', None):
            result[key] = None
        else:
            try:
                index = int(value)
                if isinstance(value, bool) or str(index) != str(value) or not 0 <= index < width:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValidationError('Wybrana kolumna nie istnieje.') from None
            result[key] = index
    if result['date'] is None or (result['amount'] is None and result['credit'] is None and result['debit'] is None):
        raise ValidationError('Wskaż datę i kwotę albo kolumny uznania i obciążenia.')
    used = [i for i in result.values() if i is not None]
    if len(used) != len(set(used)):
        raise ValidationError('Jedna kolumna nie może oznaczać dwóch różnych pól.')
    return result


def parse_bank_row(cells, mapping, width):
    def cell(key):
        index = mapping[key]
        return cells[index].strip() if index is not None and index < len(cells) else ''
    errors = []
    result = dict(date='', amount_cents=0, kind='EXPENSE', description=cell('description')[:150],
                  merchant=cell('merchant')[:150], reference=cell('reference')[:200], currency=cell('currency').upper() or 'PLN')
    if len(cells) != width:
        errors.append('Liczba pól nie zgadza się z nagłówkiem.')
    try:
        result['date'] = parsed_date(cell('date'))
        if mapping['amount'] is not None:
            value = number(cell('amount'))
        else:
            credit = number(cell('credit')) if cell('credit') else 0
            debit = number(cell('debit')) if cell('debit') else 0
            if credit < 0 or debit < 0 or (credit and debit):
                raise ValidationError('Uznanie i obciążenie powinny być dodatnie; tylko jedno może być niezerowe.')
            value = credit - debit
        if not value:
            raise ValidationError('Operacja nie może mieć zerowej kwoty.')
        result.update(amount_cents=abs(value), kind='INCOME' if value > 0 else 'EXPENSE')
        if result['currency'] != 'PLN':
            raise ValidationError('Wskaż kwotę zaksięgowaną w PLN. Nie przeliczamy kwoty walutowej automatycznie.')
    except ValidationError as error:
        errors.append(error.message)
    result['description'] = result['description'] or result['merchant'] or 'Operacja z wyciągu'
    description = normalized(result['description']+' '+result['merchant'])
    result['card_payment_hint'] = bool(re.search(r'\bsplata\b.*\b(karty|kart|kredytowki)\b', description)) or any(
        s in description for s in ('credit card payment', 'card repayment'))
    result['transfer_hint'] = result['card_payment_hint'] or any(s in description
                                  for s in ('przelew wlasny', 'na wlasny rachunek', 'internal transfer', 'own account'))
    result.update(errors=errors, category_id=None, target_account_id=None, warnings=[])
    return result


def parse_receipt(text):
    if not isinstance(text, str) or len(text) > 60000:
        raise ValidationError('Tekst paragonu może mieć najwyżej 60 000 znaków.')
    # OCR can split columns or insert spaces/apostrophes inside prices.
    rows = [re.sub(r"(?<=\d)['’](?=[,.])", '', r.strip()) for r in text.splitlines() if r.strip()]
    rows = [re.sub(r'(\d)\s*([,.])\s*(\d{2})(?!\d)', r'\1\2\3', r) for r in rows]
    total, subtotal, day, products, warnings = None, None, '', [], []
    money = re.compile(r'(?<![\d.,])\d+[,.]\d{2}(?!\d)')
    totals = []
    for index, row in enumerate(rows):
        key = normalized(row)
        priority = 0
        if re.search(r'\bdo zap[lł]?aty\b|\bdo zap[eę]aty\b|\btotal\b', key):
            priority = 3
        elif re.search(r'\b(suma|suha) (pln|zl)\b|^razem\b', key):
            priority = 2
        elif re.search(r'\bkarta\b|\bgotowka\b', key):
            priority = 1
        if priority:
            amounts = money.findall(row)
            # A following amount-only row belongs to the preceding total label.
            if not amounts and index+1 < len(rows) and re.fullmatch(r'\d+[,.]\d{2}\s*(?:PLN|zł)?', rows[index+1], re.I):
                amounts = money.findall(rows[index+1])
            if amounts:
                try:
                    value = number(amounts[-1], signed=False)
                    totals.append((priority, value))
                    if priority == 2:
                        subtotal = value
                except ValidationError:
                    pass
        match = re.search(r'\b(?:\d{4}[-.]\d{2}[-.]\d{2}|\d{2}[./-]\d{2}[./-]\d{4})\b', row)
        if match and not day:
            try: day = parsed_date(match[0])
            except ValidationError: pass
    if totals:
        best_priority = max(priority for priority, _ in totals)
        values = {value for priority, value in totals if priority == best_priority}
        if len(values) == 1:
            total = values.pop()
        else:
            warnings.append('Odczytano różne kwoty płatności. Sprawdź kwotę do zapłaty.')
    fiscal = next((i for i, row in enumerate(rows) if 'paragon' in normalized(row) or 'fiskalny' in normalized(row)), None)
    sales_end = next((i for i, row in enumerate(rows) if normalized(row).startswith(('sprzed', 'sprzeo', 'ptu', 'vat', 'suma pln', 'suha pln'))), len(rows))
    for index, row in enumerate(rows):
        key = normalized(row)
        deposit = 'kaucja' in key
        if fiscal is not None and (index <= fiscal or index >= sales_end) and not deposit:
            continue
        if re.search(r'\b(suma|suha|razem|total|zaplaty|vat|ptu|nip|karta|gotowka|reszta|rabat|upust|fiskalny|terminal)\b', key) or key.startswith(('sprzed','sprzeo','opako','ul ','bdo','boo','nr ','kasjer')):
            continue
        # A price must follow a product name. A capacity like "0,5 L" is not money.
        match = re.search(r'(?P<amount>\d+[,.]\d{2})\s*[A-G€]?[\W_]*$', row)
        if not match and deposit and index+1 < len(rows) and re.fullmatch(r'\d+[,.]\d{2}', rows[index+1]):
            row += ' '+rows[index+1]
            match = re.search(r'(?P<amount>\d+[,.]\d{2})$', row)
        if match and len(products) < 100:
            try:
                quantity_price = re.search(r'\b(\d+)\s*[xX*]\s*(\d+[,.]\d{2})', row)
                if quantity_price and int(quantity_price[1]) > 1 and quantity_price.end() >= match.end():
                    continue  # A unit price is insufficient for a multi-item line.
                amount = number(match['amount'], signed=False)
                label = row[:match.start()].strip()
                # Strip quantity, unit price and fiscal tax marker from the label.
                label = re.sub(r'\s+(?:[A-G]\s+)?(?:\d+\s*)?[xX*]\s*.*$', '', label)
                label = re.sub(r'\s+[A-G]\s+\d+(?:\s+[xX*„]?\s*\d+[,.]\d{2}[A-G]?)?$', '', label)
                label = re.sub(r'\s+[A-G]$', '', label).strip()[:120]
                if deposit:
                    label = 'Kaucja'
                if len(label) >= 2 and re.search(r'[a-zA-Ząęłńóśźż]', label, re.I):
                    products.append(dict(label=label, amount=amount/100, category_id=None))
            except ValidationError:
                pass
    product_sum = sum(round(p['amount']*100) for p in products)
    has_deposit_section = any('kaucja' in normalized(r) or normalized(r).startswith(('opakowania','opakouania','opakouanja')) for r in rows)
    if total and subtotal and total > subtotal and product_sum == subtotal and has_deposit_section and not any('kaucja' in normalized(p['label']) for p in products):
        products.append(dict(label='Kaucja / opakowania zwrotne', amount=(total-subtotal)/100, category_id=None))
        warnings.append('Kwotę kaucji ustalono z różnicy między sumą zakupów a kwotą do zapłaty. Sprawdź ją na zdjęciu.')
    if total is None:
        warnings.append('Nie rozpoznano jednoznacznej sumy. Podaj kwotę z paragonu.')
    if not day:
        warnings.append('Sprawdź datę zakupu; nie udało się jej odczytać.')
    if products and total is not None and sum(round(p['amount']*100) for p in products) != total:
        warnings.append('Suma odczytanych pozycji różni się od kwoty paragonu. Sprawdź produkty i rabaty albo przypisz cały zakup do jednej kategorii.')
    if not products:
        warnings.append('Nie rozpoznano pozycji. Możesz wpisać je ręcznie albo przypisać cały zakup do jednej kategorii.')
    merchant = next((r[:150] for r in rows[:6] if not re.search(r'\b(nip|paragon|fiskalny|tel|www|ul|bdo|boo|nr)\b', normalized(r)) and not re.search(r'\d', r) and len(r) > 2), '')
    if not merchant:
        warnings.append('Nie rozpoznano nazwy sklepu. Uzupełnij ją przed zapisem.')
    return dict(merchant=merchant, date=day, amount=total/100 if total is not None else None, lines=products), warnings

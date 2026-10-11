"""Investment reasoning records. No trading, valuation or network operations."""
import json
import re
from datetime import date, datetime, timezone

from api.exceptions import ApiError, NotFoundError, ValidationError
from database import get_db

KINDS = ('IDEA', 'BUY', 'ADD', 'HOLD', 'REDUCE', 'SELL', 'NOTE')
STATUSES = ('WATCHING', 'ACTIVE', 'CLOSED')
OUTCOMES = ('NOTE', 'CONFIRMED', 'CHANGED', 'INVALIDATED')
FIELDS = ('title', 'entry_date', 'kind', 'status', 'ticker', 'portfolio_id', 'confidence', 'thesis', 'risks', 'invalidation', 'exit_plan', 'review_date', 'tags')


def _text(data, key, maximum, required=False):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        raise ValidationError(f'Pole {key}: wymagany tekst, maksymalnie {maximum} znaków.')
    return value.strip()


def _day(value, label, optional=False):
    if optional and value in (None, ''):
        return None
    try:
        day = date.fromisoformat(value)
        if day.isoformat() != value or not date(2000, 1, 1) <= day <= date(date.today().year + 10, 12, 31):
            raise ValueError()
        return day.isoformat()
    except (ValueError, TypeError):
        raise ValidationError(f'{label}: podaj poprawną datę YYYY-MM-DD.') from None


def _choice(value, choices, label):
    if not isinstance(value, str) or value not in choices:
        raise ValidationError(f'{label}: wybierz jedną z dostępnych opcji.')
    return value


def _entry(entry_id):
    row = get_db().execute('SELECT * FROM investor_journal WHERE id=?', (entry_id,)).fetchone()
    if not row:
        raise NotFoundError('Wpis dziennika nie istnieje.')
    return dict(row)


def _version(data, entry):
    version = data.get('version')
    if type(version) is not int or version < 1:
        raise ValidationError('Brak prawidłowej wersji wpisu. Wczytaj wpis ponownie.')
    if version != entry['version']:
        raise ApiError('journal_conflict', 'Ten wpis został już zmieniony. Wczytaj jego aktualną wersję przed ponownym zapisem.', status=409)


def _revision(entry_id, reason, now):
    entry = _entry(entry_id)
    get_db().execute('INSERT INTO investor_journal_revisions(entry_id,version,reason,snapshot,created_at) VALUES (?,?,?,?,?)',
                     (entry_id, entry['version'], reason, json.dumps(entry, ensure_ascii=False), now))


def _serialize(row):
    item = dict(row)
    item['tags'] = json.loads(item['tags'])
    item['is_archived'] = bool(item['is_archived'])
    item['review_due'] = bool(not item['is_archived'] and item['status'] != 'CLOSED' and item['review_date'] and item['review_date'] <= date.today().isoformat())
    return item


def _rows():
    return [_serialize(row) for row in get_db().execute('''SELECT j.*,p.name AS portfolio_name,p.is_archived AS portfolio_archived,
        (SELECT COUNT(*) FROM investor_journal_reviews r WHERE r.entry_id=j.id) AS review_count
        FROM investor_journal j LEFT JOIN portfolios p ON p.id=j.portfolio_id ORDER BY j.entry_date DESC,j.id DESC''')]


def detail(entry_id):
    row = get_db().execute('''SELECT j.*,p.name AS portfolio_name,p.is_archived AS portfolio_archived,
        (SELECT COUNT(*) FROM investor_journal_reviews r WHERE r.entry_id=j.id) AS review_count
        FROM investor_journal j LEFT JOIN portfolios p ON p.id=j.portfolio_id WHERE j.id=?''', (entry_id,)).fetchone()
    if row is None:
        raise NotFoundError('Wpis dziennika nie istnieje.')
    entry = _serialize(row)
    entry['reviews'] = [dict(row) for row in get_db().execute('SELECT * FROM investor_journal_reviews WHERE entry_id=? ORDER BY review_date DESC,id DESC', (entry_id,))]
    entry['revisions'] = [{'version':row['version'], 'reason':row['reason'], 'created_at':row['created_at'], 'snapshot':_serialize(json.loads(row['snapshot']))}
                          for row in get_db().execute('SELECT * FROM investor_journal_revisions WHERE entry_id=? ORDER BY version DESC', (entry_id,))]
    return entry


def workspace(args):
    query = str(args.get('q', '')).strip().casefold()
    if len(query) > 200:
        raise ValidationError('Wyszukiwanie może mieć najwyżej 200 znaków.')
    status = args.get('status', 'all')
    kind = args.get('kind', 'all')
    archived = args.get('archived', '0')
    due = args.get('due', '0')
    if status not in ('all', *STATUSES) or kind not in ('all', *KINDS) or archived not in ('0', '1') or due not in ('0', '1'):
        raise ValidationError('Nieprawidłowy filtr dziennika.')
    try:
        page = int(args.get('page', '1'))
        portfolio = int(args['portfolio']) if args.get('portfolio') else None
        if page < 1 or (portfolio is not None and portfolio < 1):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('Nieprawidłowy numer strony lub portfela.') from None
    ticker = str(args.get('ticker', '')).strip().upper()
    tag = str(args.get('tag', '')).strip().casefold()
    rows = _rows()
    active = [row for row in rows if not row['is_archived']]
    stats = {'active':sum(row['status'] == 'ACTIVE' for row in active), 'watching':sum(row['status'] == 'WATCHING' for row in active),
             'closed':sum(row['status'] == 'CLOSED' for row in active), 'due':sum(row['review_due'] for row in active), 'archived':len(rows) - len(active)}
    filtered = [row for row in rows if row['is_archived'] == (archived == '1')
                and (status == 'all' or row['status'] == status) and (kind == 'all' or row['kind'] == kind)
                and (not portfolio or row['portfolio_id'] == portfolio) and (not ticker or row['ticker'] == ticker)
                and (not tag or tag in [value.casefold() for value in row['tags']]) and (due == '0' or row['review_due'])
                and (not query or query in ' '.join(str(row.get(key) or '') for key in ('title','ticker','portfolio_name','thesis','risks','invalidation','exit_plan','tags')).casefold())]
    portfolios = [dict(row) for row in get_db().execute('SELECT id,name,is_archived FROM portfolios ORDER BY is_archived,name')]
    return {'entries':filtered[(page - 1) * 50:page * 50], 'total':len(filtered), 'page':page, 'page_size':50,
            'stats':stats, 'portfolios':portfolios, 'tags':sorted({tag for row in active for tag in row['tags']}, key=str.casefold), 'as_of':date.today().isoformat()}


def _validate(data, old=None):
    item = {key:_text(data, key, 5000) for key in ('thesis','risks','invalidation','exit_plan')}
    item['title'] = _text(data, 'title', 150, True)
    item['entry_date'] = _day(data.get('entry_date'), 'Data decyzji')
    if item['entry_date'] > date.today().isoformat():
        raise ValidationError('Data wpisu nie może być w przyszłości.')
    item['review_date'] = _day(data.get('review_date'), 'Termin przeglądu', True)
    if item['review_date'] and item['review_date'] < item['entry_date']:
        raise ValidationError('Termin przeglądu nie może poprzedzać decyzji.')
    item['kind'] = _choice(data.get('kind'), KINDS, 'Rodzaj decyzji')
    item['status'] = _choice(data.get('status'), STATUSES, 'Status tezy')
    ticker = data.get('ticker')
    if ticker not in (None, ''):
        if not isinstance(ticker, str) or not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^=_/\-]{0,39}', ticker.strip().upper()):
            raise ValidationError('Podaj prawidłowy symbol instrumentu, np. CSPX.L.')
        ticker = ticker.strip().upper()
    item['ticker'] = ticker or None
    portfolio = data.get('portfolio_id')
    if portfolio is not None:
        if type(portfolio) is not int or portfolio < 1:
            raise ValidationError('Wybierz prawidłowy portfel.')
        row = get_db().execute('SELECT is_archived FROM portfolios WHERE id=?', (portfolio,)).fetchone()
        if not row or (row['is_archived'] and (not old or old['portfolio_id'] != portfolio)):
            raise ValidationError('Portfel nie istnieje lub jest w archiwum.')
    item['portfolio_id'] = portfolio
    confidence = data.get('confidence')
    if confidence is not None and (type(confidence) is not int or not 1 <= confidence <= 5):
        raise ValidationError('Pewność tezy musi być liczbą od 1 do 5.')
    item['confidence'] = confidence
    tags = data.get('tags', [])
    if not isinstance(tags, list) or len(tags) > 8 or any(not isinstance(tag, str) or not 1 <= len(tag.strip()) <= 25 for tag in tags):
        raise ValidationError('Dodaj najwyżej 8 etykiet, po 1–25 znaków.')
    seen = set(); unique = []
    for tag in tags:
        tag = tag.strip()
        if tag.casefold() not in seen:
            unique.append(tag); seen.add(tag.casefold())
    item['tags'] = json.dumps(unique, ensure_ascii=False)
    return item


def save(data, entry_id=None):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        # Serialize modifications and revision checks into one transaction.
        db.execute('BEGIN IMMEDIATE')
        old = _entry(entry_id) if entry_id is not None else None
        if old:
            _version(data, old)
        item = _validate(data, old)
        if old:
            latest_review = db.execute('SELECT MIN(review_date) AS first FROM investor_journal_reviews WHERE entry_id=?', (entry_id,)).fetchone()['first']
            if latest_review and item['entry_date'] > latest_review:
                raise ValidationError('Data decyzji nie może być późniejsza niż jej zapisane przeglądy.')
            db.execute(f'UPDATE investor_journal SET {",".join(key+"=?" for key in FIELDS)},version=version+1,updated_at=? WHERE id=?',
                       (*[item[key] for key in FIELDS], now, entry_id))
        else:
            entry_id = db.execute(f'INSERT INTO investor_journal({",".join(FIELDS)},created_at,updated_at) VALUES ({",".join("?" for _ in FIELDS)},?,?)',
                                  (*[item[key] for key in FIELDS], now, now)).lastrowid
        _revision(entry_id, 'edit' if old else 'create', now)
        db.commit()
    except Exception:
        db.rollback(); raise
    return {'id':entry_id}


def archive(entry_id, data):
    db = get_db(); now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute('BEGIN IMMEDIATE')
        old = _entry(entry_id); _version(data, old)
        archived = data.get('archived')
        if type(archived) is not bool:
            raise ValidationError('Wybierz archiwizację lub przywrócenie wpisu.')
        if bool(old['is_archived']) != archived:
            db.execute('UPDATE investor_journal SET is_archived=?,version=version+1,updated_at=? WHERE id=?', (int(archived),now,entry_id))
            _revision(entry_id, 'archive' if archived else 'restore', now)
        db.commit()
    except Exception:
        db.rollback(); raise
    return {'id':entry_id}


def add_review(entry_id, data):
    db = get_db(); now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute('BEGIN IMMEDIATE')
        old = _entry(entry_id); _version(data, old)
        if old['is_archived']:
            raise ValidationError('Przywróć wpis z archiwum przed dodaniem przeglądu.')
        day = _day(data.get('review_date'), 'Data przeglądu')
        if not old['entry_date'] <= day <= date.today().isoformat():
            raise ValidationError('Przegląd musi przypadać pomiędzy datą decyzji a dzisiaj.')
        outcome = _choice(data.get('outcome'), OUTCOMES, 'Ocena tezy')
        notes = _text(data, 'notes', 5000, True)
        lessons = _text(data, 'lessons', 5000)
        next_day = _day(data.get('next_review_date'), 'Kolejny termin', True)
        if next_day and next_day < day:
            raise ValidationError('Kolejny termin nie może poprzedzać tego przeglądu.')
        status = _choice(data.get('entry_status'), STATUSES, 'Status po przeglądzie')
        # Backdated reviews are history only; don't overwrite a newer review's schedule.
        latest = db.execute('SELECT MAX(review_date) AS latest FROM investor_journal_reviews WHERE entry_id=?', (entry_id,)).fetchone()['latest']
        review_id = db.execute('''INSERT INTO investor_journal_reviews(entry_id,review_date,outcome,notes,lessons,next_review_date,entry_status,created_at)
            VALUES (?,?,?,?,?,?,?,?)''', (entry_id,day,outcome,notes,lessons,next_day,status,now)).lastrowid
        if latest is None or day >= latest:
            db.execute('UPDATE investor_journal SET status=?,review_date=?,version=version+1,updated_at=? WHERE id=?', (status,next_day,now,entry_id))
        else:
            db.execute('UPDATE investor_journal SET version=version+1,updated_at=? WHERE id=?', (now,entry_id))
        _revision(entry_id, 'review', now)
        db.commit()
    except Exception:
        db.rollback(); raise
    return {'id':review_id, 'entry_id':entry_id}


def export():
    return {'schema_version':1, 'exported_at':datetime.now(timezone.utc).isoformat(), 'entries':[detail(row['id']) for row in _rows()]}

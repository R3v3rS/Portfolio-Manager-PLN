"""Public research inbox. No trades, portfolio writes or inferred buy ratings."""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import requests
from api.exceptions import NotFoundError, ValidationError
from database import get_db

SOURCES = {
    'podlacki': dict(name='Marcin Podlacki', kind='youtube',
                    url='https://www.youtube.com/@MarcinPodlacki',
                    feed='https://www.youtube.com/feeds/videos.xml?channel_id=UChLwJNFJURZxzAAPEsrnxfQ'),
    'zawod': dict(name='Zawód Inwestor', kind='youtube',
                 url='https://www.youtube.com/@zawodinwestor',
                 feed='https://www.youtube.com/feeds/videos.xml?channel_id=UCG4T6bLDq2TdAdRAp2GDOCw'),
    'comparic': dict(name='Podlacki · omówienia Comparic', kind='rss',
                    url='https://comparic.pl/', feed='https://comparic.pl/feed/'),
}
OPINIONS = {'MENTION', 'WATCH', 'HOLD', 'BUY', 'SELL'}
STAGES = {'NEW', 'ANALYZING', 'WATCHING', 'REJECTED'}


def init_schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS research_sources (
            id TEXT PRIMARY KEY, checked_at TEXT, status TEXT NOT NULL DEFAULT 'never', message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS research_publications (
            id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL,
            title TEXT NOT NULL, published_on TEXT NOT NULL, excerpt TEXT NOT NULL DEFAULT '',
            publisher TEXT NOT NULL DEFAULT '', provenance TEXT NOT NULL,
            suggestions TEXT NOT NULL DEFAULT '[]', captured_at TEXT NOT NULL,
            UNIQUE(source_id,url)
        );
        CREATE INDEX IF NOT EXISTS idx_research_publications_month ON research_publications(published_on);
        CREATE TABLE IF NOT EXISTS research_ideas (
            id INTEGER PRIMARY KEY, publication_id INTEGER NOT NULL REFERENCES research_publications(id),
            ticker TEXT NOT NULL, opinion TEXT NOT NULL DEFAULT 'MENTION',
            stage TEXT NOT NULL DEFAULT 'NEW', thesis TEXT NOT NULL DEFAULT '', risks TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL DEFAULT '', horizon TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(publication_id,ticker)
        );
    ''')
    db.executemany('INSERT OR IGNORE INTO research_sources(id) VALUES(?)', [(key,) for key in SOURCES])


def now():
    return datetime.now(timezone.utc).isoformat()


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('p', 'br', 'li', 'div'): self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
        self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def plain(text):
    parser = PlainText(); parser.feed(text or '')
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c)).replace('ł','l')


def canonical_url(value, source_id):
    if not isinstance(value, str) or len(value) > 2048: raise ValidationError('Podaj poprawny link do materiału.')
    try:
        parts = urlsplit(value.strip())
        if parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None,443): raise ValueError()
        host = (parts.hostname or '').lower()
        if source_id == 'comparic':
            if host not in ('comparic.pl','www.comparic.pl') or not parts.path.strip('/'): raise ValueError()
            return urlunsplit(('https','comparic.pl',parts.path,'',''))
        if host == 'youtu.be': video = parts.path.strip('/')
        elif host in ('youtube.com','www.youtube.com','m.youtube.com'):
            video = parse_qs(parts.query).get('v',[''])[0] if parts.path == '/watch' else parts.path.split('/')[-1] if parts.path.startswith(('/shorts/','/live/')) else ''
        else: raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',video): raise ValueError()
        return 'https://www.youtube.com/watch?' + urlencode({'v':video})
    except ValueError:
        raise ValidationError('Użyj linku do filmu YouTube albo artykułu Comparic zgodnego z wybranym źródłem.') from None


def published_day(value):
    try:
        stamp = datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError, AttributeError):
        try: stamp = parsedate_to_datetime(value)
        except (ValueError, TypeError): return None
    day = stamp.date().isoformat()
    return day if day <= date.today().isoformat() else None


def suggestions(text):
    """Only suggest known instruments; humans assign the opinion and ticker."""
    found = set(); normalized = fold(text)
    db = get_db()
    rows = db.execute('SELECT ticker,company_name FROM asset_metadata').fetchall()
    for row in rows:
        symbol = row['ticker'].split('.')[0]
        if symbol == 'GPW' and not re.search(r'akcje gpw|spolka gpw|gpw\.wa',normalized): continue
        name = fold(row['company_name'] or '')
        if (len(symbol) >= 3 and re.search(r'(?<!\w)' + re.escape(symbol.lower()) + r'(?!\w)', normalized)) or (len(name) >= 5 and name in normalized):
            found.add(row['ticker'])
    for row in db.execute('SELECT symbol_input,ticker FROM symbol_mappings'):
        if row['ticker']=='GPW.WA' and not re.search(r'akcje gpw|spolka gpw|gpw\.wa',normalized): continue
        alias = fold(row['symbol_input'])
        if len(alias) >= 3 and re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', normalized): found.add(row['ticker'])
    return sorted(found)[:15]


def fetch_feed(url):
    # Only fixed, maintained public feeds are fetched. User-supplied links are never requested.
    with requests.get(url, timeout=(5,12), stream=True, allow_redirects=False,
                      headers={'User-Agent':'PortfolioManagerResearch/1.0'}) as response:
        response.raise_for_status()
        if response.status_code != 200: raise ValueError('Unavailable feed')
        body = bytearray()
        for part in response.iter_content(65536):
            body.extend(part)
            if len(body) > 1_000_000: raise ValueError('Feed too large')
        return bytes(body)


def parse_feed(raw, source_id):
    markup = raw.replace(b'\x00',b'').upper()
    if b'<!DOCTYPE' in markup or b'<!ENTITY' in markup: raise ValueError('Unsafe XML')
    root = ET.fromstring(raw)
    source = SOURCES[source_id]; output = []
    atom = '{http://www.w3.org/2005/Atom}'; media = '{http://search.yahoo.com/mrss/}'
    entries = root.findall(atom+'entry') if source['kind']=='youtube' else root.findall('./channel/item')
    for item in entries[:80]:
        if source['kind']=='youtube':
            title = item.findtext(atom+'title','')
            day = published_day(item.findtext(atom+'published',''))
            link = next((x.attrib.get('href','') for x in item.findall(atom+'link') if x.attrib.get('rel')=='alternate'),'')
            content = item.findtext(media+'group/'+media+'description','')
            publisher = item.findtext(atom+'author/'+atom+'name',source['name'])
        else:
            title = item.findtext('title',''); day = published_day(item.findtext('pubDate',''))
            link = item.findtext('link','')
            content = item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded','') or item.findtext('description','')
            publisher = item.findtext('{http://purl.org/dc/elements/1.1/}creator','Comparic')
            if 'podlacki' not in fold(title+' '+plain(content)+' '+publisher): continue
        if not title or not day: continue
        try: url = canonical_url(link,source_id)
        except ValidationError: continue
        text = plain(content)
        output.append(dict(source_id=source_id,url=url,title=plain(title)[:400],published_on=day,
                           excerpt=text[:1600],publisher=plain(publisher)[:150],provenance='FEED',
                           suggestions=json.dumps(suggestions(title if source['kind']=='youtube' else title+' '+text)),captured_at=now()))
    return output


def store_publication(data):
    db = get_db()
    db.execute('''INSERT OR IGNORE INTO research_publications
        (source_id,url,title,published_on,excerpt,publisher,provenance,suggestions,captured_at)
        VALUES(:source_id,:url,:title,:published_on,:excerpt,:publisher,:provenance,:suggestions,:captured_at)''',data)
    return db.execute('SELECT id FROM research_publications WHERE source_id=? AND url=?',(data['source_id'],data['url'])).fetchone()['id']


def refresh():
    db = get_db(); output = []
    for key, source in SOURCES.items():
        old = db.execute('SELECT * FROM research_sources WHERE id=?',(key,)).fetchone()
        if old['checked_at'] and (datetime.now(timezone.utc)-datetime.fromisoformat(old['checked_at'])).total_seconds()<60:
            output.append(dict(source_id=key,status=old['status'],message='Źródło sprawdzono przed chwilą.')); continue
        try:
            publications = parse_feed(fetch_feed(source['feed']),key)
            before = db.total_changes
            for item in publications: store_publication(item)
            added = db.total_changes-before
            status = 'ok'; message = f'Nowych materiałów: {added}. Odczytanych: {len(publications)}.'
        except (requests.RequestException,ValueError,ET.ParseError):
            db.rollback()
            status = 'unavailable'; message = 'Źródło chwilowo niedostępne. Zachowano wcześniejsze materiały; możesz dodać link ręcznie.'
        db.execute('UPDATE research_sources SET checked_at=?,status=?,message=? WHERE id=?',(now(),status,message,key))
        db.commit(); output.append(dict(source_id=key,status=status,message=message))
    return output


def text_field(data,key,limit,required=False):
    value = data.get(key,'')
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()): raise ValidationError('Sprawdź pole: '+key)
    return value.strip()


def add_publication(data):
    key = data.get('source_id')
    if not isinstance(key,str) or key not in SOURCES: raise ValidationError('Wybierz źródło materiału.')
    day = data.get('published_on','')
    try:
        if date.fromisoformat(day).isoformat()!=day or day>date.today().isoformat(): raise ValueError()
    except (ValueError,TypeError): raise ValidationError('Podaj datę publikacji, nie późniejszą niż dziś.') from None
    item = dict(source_id=key,url=canonical_url(data.get('url'),key),title=text_field(data,'title',400,True),
                published_on=day,excerpt='',publisher='',provenance='MANUAL',suggestions='[]',captured_at=now())
    db = get_db(); identifier = store_publication(item); db.commit(); return {'id':identifier}


def save_idea(data, idea_id=None):
    db = get_db()
    if idea_id:
        existing = db.execute('SELECT * FROM research_ideas WHERE id=?',(idea_id,)).fetchone()
        if not existing: raise NotFoundError('Nie znaleziono analizy.')
        data = {**dict(existing),**data}
    pid = data.get('publication_id')
    if type(pid) is not int or not db.execute('SELECT id FROM research_publications WHERE id=?',(pid,)).fetchone(): raise ValidationError('Wybierz zapisany materiał.')
    ticker = text_field(data,'ticker',32,True).upper()
    if not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^=_-]{0,31}',ticker): raise ValidationError('Podaj poprawny ticker.')
    opinion = data.get('opinion','MENTION'); stage = data.get('stage','NEW')
    if not isinstance(opinion,str) or not isinstance(stage,str) or opinion not in OPINIONS or stage not in STAGES: raise ValidationError('Wybierz poprawną opinię i status.')
    fields = {key:text_field(data,key,4000 if key in ('thesis','risks') else 1000) for key in ('thesis','risks','evidence','horizon')}
    if opinion!='MENTION' and not fields['evidence']: raise ValidationError('Dodaj fragment lub moment wypowiedzi potwierdzający opinię autora.')
    duplicate = db.execute('SELECT id FROM research_ideas WHERE publication_id=? AND ticker=?',(pid,ticker)).fetchone()
    if duplicate and duplicate['id']!=idea_id: raise ValidationError('Ta spółka ma już analizę dla tego materiału.')
    values = dict(publication_id=pid,ticker=ticker,opinion=opinion,stage=stage,**fields,updated_at=now())
    if idea_id:
        db.execute('''UPDATE research_ideas SET publication_id=:publication_id,ticker=:ticker,opinion=:opinion,
            stage=:stage,thesis=:thesis,risks=:risks,evidence=:evidence,horizon=:horizon,updated_at=:updated_at WHERE id=:id''',{**values,'id':idea_id})
    else:
        idea_id = db.execute('''INSERT INTO research_ideas(publication_id,ticker,opinion,stage,thesis,risks,evidence,horizon,created_at,updated_at)
            VALUES(:publication_id,:ticker,:opinion,:stage,:thesis,:risks,:evidence,:horizon,:updated_at,:updated_at)''',values).lastrowid
    db.commit(); return {'id':idea_id}


def workspace(month=None):
    if month and not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month): raise ValidationError('Wybierz poprawny miesiąc.')
    db = get_db()
    rows = db.execute('SELECT * FROM research_publications WHERE (? IS NULL OR substr(published_on,1,7)=?) ORDER BY published_on DESC,id DESC',(month,month)).fetchall()
    publications = [{**dict(row),'suggestions':suggestions(row['title'] if row['source_id']!='comparic' else row['title']+' '+row['excerpt'])
                     if row['provenance']=='FEED' else []} for row in rows]
    ideas = [dict(row) for row in db.execute('''SELECT i.*,p.source_id,p.title,p.url,p.published_on FROM research_ideas i
        JOIN research_publications p ON p.id=i.publication_id
        WHERE (? IS NULL OR substr(p.published_on,1,7)=?) ORDER BY i.updated_at DESC''',(month,month))]
    held = {row['ticker'] for row in db.execute('SELECT DISTINCT ticker FROM holdings WHERE quantity>0')}
    watched = {row['ticker'] for row in db.execute('SELECT ticker FROM watchlist')}
    metadata = {row['ticker']:row['company_name'] for row in db.execute('SELECT ticker,company_name FROM asset_metadata')}
    for idea in ideas:
        ticker = idea['ticker']; idea.update(is_held=ticker in held,is_watched=ticker in watched,company_name=metadata.get(ticker,ticker))
    sources = [{**SOURCES[row['id']],**dict(row)} for row in db.execute('SELECT * FROM research_sources ORDER BY rowid')]
    for source in sources: source.pop('feed',None)
    return dict(sources=sources,publications=publications,ideas=ideas,
                months=[row[0] for row in db.execute('SELECT DISTINCT substr(published_on,1,7) FROM research_publications ORDER BY 1 DESC')],
                instruments=[dict(row) for row in db.execute('SELECT ticker,company_name FROM asset_metadata ORDER BY ticker')],
                as_of=date.today().isoformat())

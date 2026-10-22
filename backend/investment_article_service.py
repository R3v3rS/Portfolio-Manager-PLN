"""Read public article bodies only from maintained source domains, without redirects."""
import requests
from api.exceptions import ApiError, ValidationError
from database import get_db
from investment_ideas_service import SOURCES, canonical_url, now
from investment_material_service import publication

def saved(pid):
    publication(pid)
    row=get_db().execute('SELECT * FROM research_publication_text WHERE publication_id=?',(pid,)).fetchone()
    return {**dict(row),'truncated':bool(row['truncated'])} if row else None

def fetch(pid):
    from bs4 import BeautifulSoup
    p=publication(pid)
    if SOURCES[p['source_id']]['kind']!='rss':
        raise ValidationError('To film. Wklej transkrypcję lub wybierz analizę filmu.')
    url=canonical_url(p['url'],p['source_id'])
    try:
        with requests.get(url,timeout=(5,20),stream=True,allow_redirects=False,
                          headers={'User-Agent':'PortfolioManagerResearch/1.0'}) as response:
            response.raise_for_status()
            if response.status_code!=200 or 'text/html' not in response.headers.get('Content-Type','').lower():
                raise ValueError('No public HTML')
            body=bytearray()
            for part in response.iter_content(65536):
                body.extend(part)
                if len(body)>3_000_000:raise ValueError('Too large')
        soup=BeautifulSoup(bytes(body),'html.parser')
        nodes=soup.select('.entry-content, .td-post-content, .tdb_single_content, [itemprop="articleBody"]')
        if not nodes:raise ValueError('No article body')
        node=max(nodes,key=lambda n:len(n.get_text()))
        for element in node.select('script,style,nav,form,aside,iframe,.sharedaddy,.related-posts,.advertisement'):
            element.decompose()
        text=node.get_text('\n',strip=True)
        if len(text)<400:raise ValueError('Only teaser')
    except (requests.RequestException,ValueError):
        raise ApiError('article_unavailable','Nie udało się pobrać publicznej treści artykułu. Otwórz źródło i wklej dostępny fragment; zapisane analizy pozostają bez zmian.',status=502) from None
    db=get_db()
    db.execute('''INSERT INTO research_publication_text(publication_id,text,source_url,captured_at,truncated)
        VALUES(?,?,?,?,?) ON CONFLICT(publication_id) DO UPDATE SET text=excluded.text,
        source_url=excluded.source_url,captured_at=excluded.captured_at,truncated=excluded.truncated''',
        (pid,text[:60000],url,now(),int(len(text)>60000)))
    db.commit()
    return saved(pid)

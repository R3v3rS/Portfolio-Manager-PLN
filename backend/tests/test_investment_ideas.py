import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from database import init_db,get_db
from api.exceptions import ValidationError,NotFoundError
from api.response import error_response
from routes_investment_ideas import ideas_bp
import investment_ideas_service as service

DAY=date.today().isoformat()
VIDEO='https://www.youtube.com/watch?v=abcdefghijk'

def atom(title='PZU i strategia',day=DAY):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
        <entry><title>{title}</title><published>{day}T10:00:00Z</published>
        <link rel="alternate" href="{VIDEO.replace('&','&amp;')}"/><author><name>Test channel</name></author>
        <media:group><media:description>Rozmowa o PZU. Nie podano decyzji.</media:description></media:group></entry></feed>'''.encode()

class InvestmentIdeasTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Flask(__name__);self.app.config.update(TESTING=True,DATABASE=str(Path(self.temp.name)/'ideas.db'))
        self.app.register_blueprint(ideas_bp,url_prefix='/api/investment-ideas')
        self.app.register_error_handler(ValidationError,lambda e:error_response('validation_error',e.message,status=400))
        self.app.register_error_handler(NotFoundError,lambda e:error_response('not_found',e.message,status=404))
        init_db(self.app)
        self.context=self.app.app_context();self.context.push();self.addCleanup(self.context.pop)
        self.db=get_db();self.client=self.app.test_client()
        self.db.execute("INSERT INTO asset_metadata(ticker,company_name,updated_at) VALUES('PZU.WA','Powszechny Zaklad Ubezpieczen',?)",(DAY,))
        self.db.execute("INSERT INTO portfolios(name,current_cash) VALUES('Untouched',1000)")
        self.db.commit()

    def publication(self,day=DAY):
        return service.add_publication(dict(source_id='podlacki',url=VIDEO,title='Film o PZU',published_on=day))['id']

    def test_cached_reads_do_not_fetch_or_touch_financial_data(self):
        with patch.object(service,'fetch_feed') as fetch:
            response=self.client.get('/api/investment-ideas')
            self.assertEqual(response.status_code,200);fetch.assert_not_called()
        self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios').fetchone()[0],1000)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],0)

    def test_feed_discovers_mentions_without_creating_buy_opinions(self):
        publications=service.parse_feed(atom(),'podlacki')
        self.assertEqual(json.loads(publications[0]['suggestions']),['PZU.WA'])
        service.store_publication(publications[0]);self.db.commit()
        self.assertEqual(len(service.workspace()['publications']),1)
        self.assertEqual(service.workspace()['ideas'],[])

    def test_comparic_keeps_editor_attribution_and_additional_authors(self):
        raw=f'''<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
          <item><title>Spółki omawiane przez Podlackiego</title><link>https://comparic.pl/pomysly/</link>
          <pubDate>{date.today().strftime('%a, %d %b %Y')} 10:00:00 +0000</pubDate><dc:creator>Redaktor</dc:creator><description>PZU</description></item>
          <item><title>Inny temat</title><link>https://comparic.pl/inne/</link><pubDate>{date.today().strftime('%a, %d %b %Y')} 10:00:00 +0000</pubDate></item>
          </channel></rss>'''.encode()
        rows=service.parse_feed(raw,'comparic');self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['publisher'],'Redaktor')

    def test_general_market_mentions_and_description_promotions_do_not_suggest_stocks(self):
        self.db.execute("INSERT INTO asset_metadata(ticker,company_name,updated_at) VALUES('GPW.WA','Gielda Papierow Wartosciowych',?)",(DAY,))
        self.assertEqual(service.suggestions('Dziś na GPW'),[])
        self.assertEqual(service.suggestions('Akcje GPW'),['GPW.WA'])
        raw=atom(title='Strategia inwestowania').replace(b'Rozmowa o PZU. Nie podano decyzji.',b'Reklama: oferta PZU')
        self.assertEqual(json.loads(service.parse_feed(raw,'podlacki')[0]['suggestions']),[])

    def test_duplicate_urls_keep_original_month_and_do_not_duplicate_publications(self):
        past=(date.today()-timedelta(days=40)).isoformat();identifier=self.publication(past)
        second=service.add_publication(dict(source_id='podlacki',url='https://youtu.be/abcdefghijk?t=12',title='Changed',published_on=DAY))
        self.assertEqual(identifier,second['id'])
        self.assertEqual(service.workspace(past[:7])['publications'][0]['title'],'Film o PZU')
        self.assertEqual(service.workspace(DAY[:7])['publications'],[])

    def test_opinions_need_evidence_and_updates_preserve_unique_company(self):
        pid=self.publication()
        with self.assertRaises(ValidationError):service.save_idea(dict(publication_id=pid,ticker='PZU.WA',opinion='BUY'))
        identifier=service.save_idea(dict(publication_id=pid,ticker='PZU.WA',opinion='BUY',evidence='12:35 autor deklaruje zakup',risks='Dług'))['id']
        service.save_idea(dict(stage='WATCHING'),identifier)
        row=service.workspace()['ideas'][0]
        self.assertEqual(row['stage'],'WATCHING');self.assertEqual(row['evidence'],'12:35 autor deklaruje zakup')
        self.assertEqual(row['risks'],'Dług')
        with self.assertRaises(ValidationError):service.save_idea(dict(publication_id=pid,ticker='PZU.WA'))
        self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios').fetchone()[0],1000)

    def test_partial_refresh_and_cooldown_preserve_existing_content(self):
        self.publication()
        with patch.object(service,'fetch_feed',side_effect=[b'<rss><channel/></rss>',atom(),ValueError('unavailable'),b'<rss><channel/></rss>']) as fetch:
            response=self.client.post('/api/investment-ideas/refresh',json={})
            self.assertEqual(response.status_code,200)
            statuses=[row['status'] for row in response.json['payload']['sources']]
            self.assertEqual(statuses,['ok','ok','unavailable','ok'])
            self.client.post('/api/investment-ideas/refresh',json={});self.assertEqual(fetch.call_count,4)
        self.assertEqual(len(service.workspace()['publications']),1)

    def test_urls_xml_dates_and_invalid_input_fail_safely(self):
        for url in ('http://127.0.0.1:5000','https://youtube.com.evil.test/watch?v=abcdefghijk','https://user:pass@youtube.com/watch?v=abcdefghijk','https://www.youtube.com:444/watch?v=abcdefghijk','javascript:alert(1)'):
            with self.assertRaises(ValidationError):service.canonical_url(url,'podlacki')
        for raw in (b'<!DOCTYPE rss [<!ENTITY x "oops">]><rss>&x;</rss>', '<!DOCTYPE rss><rss/>'.encode('utf-16')):
            with self.assertRaises(ValueError):service.parse_feed(raw,'comparic')
        self.assertEqual(service.plain('<script>alert(1)</script><b>PZU</b>'),'PZU')
        self.assertEqual(service.parse_feed(atom(day=(date.today()+timedelta(days=1)).isoformat()),'podlacki'),[])
        for data in ({'source_id':[]},{'source_id':'podlacki','published_on':'bad'},{}):
            self.assertEqual(self.client.post('/api/investment-ideas/publications',json=data).status_code,400)
        self.assertEqual(self.client.get('/api/investment-ideas?month=2026-99').status_code,400)
        self.assertEqual(self.client.put('/api/investment-ideas/ideas/999',json={}).status_code,404)

    def test_feed_transport_rejects_redirects_and_large_responses(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.__enter__.return_value=response;response.status_code=302
        with patch.object(service.requests,'get',return_value=response) as get:
            with self.assertRaises(ValueError):service.fetch_feed(service.SOURCES['podlacki']['feed'])
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
        response.status_code=200;response.iter_content.return_value=[b'x'*1_000_001]
        with patch.object(service.requests,'get',return_value=response):
            with self.assertRaises(ValueError):service.fetch_feed(service.SOURCES['podlacki']['feed'])

if __name__=='__main__':unittest.main()

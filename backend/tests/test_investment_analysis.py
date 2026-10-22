import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
import test_investment_corrections as fixtures
from api.exceptions import ApiError, ValidationError
from investment_ai_context import build, facts
import investment_ai_service as chat
import investment_ai_provider as provider
import investment_allocation_service as allocation
import investment_exposure_service as exposure
import investment_material_service as materials
import investment_ideas_service as ideas

class InvestmentAnalysisTests(unittest.TestCase):
    setUp=fixtures.InvestmentCorrectionsTest.setUp
    tearDown=fixtures.InvestmentCorrectionsTest.tearDown
    holding=fixtures.InvestmentCorrectionsTest.holding
    quotes=fixtures.InvestmentCorrectionsTest.quotes
    stamps=fixtures.InvestmentCorrectionsTest.stamps

    def test_shared_context_fx_missing_and_child_scope(self):
        self.holding('USD')
        child=self.db.execute("INSERT INTO portfolios(name,account_type,parent_portfolio_id,current_cash) VALUES('Child','IKE',?,25)",(self.pid,)).lastrowid
        self.db.execute("INSERT INTO transactions(portfolio_id,sub_portfolio_id,type,total_value,date,ticker,quantity,price) VALUES (?,?,'DEPOSIT',25,?,'CASH',0,0)",(self.pid,child,date.today().isoformat()));self.db.commit()
        with self.quotes({'ABC':120,'USDPLN=X':4}),self.stamps():
            whole=build(self.pid,True);own=build(self.pid,False);separate=build(child,False)
        # Shared valuation includes the configured estimated sale costs.
        self.assertAlmostEqual(whole['value']['asset_value']-own['value']['asset_value'],25)
        self.assertGreater(own['value']['asset_value'],1000)
        self.assertEqual(whole['results']['deposits'],25)
        self.assertEqual(own['results']['deposits'],0)
        self.assertEqual(separate['value']['asset_value'],25)
        self.assertEqual(separate['results']['deposits'],25)
        with self.quotes({'ABC':120}),self.stamps():
            incomplete=build(self.pid)
        self.assertIsNone(incomplete['value']['asset_value']);self.assertTrue(incomplete['warnings'])

    def test_special_accounts_have_context_without_equity_holdings(self):
        for kind in ('SAVINGS','BONDS','PPK'):
            self.db.execute('UPDATE portfolios SET account_type=? WHERE id=?',(kind,self.pid));self.db.commit()
            result=build(self.pid)
            self.assertEqual(result['positions'],[])
            self.assertTrue(any(s['id']=='account_details' for s in result['sources']))
            self.assertEqual(facts(result)['mode'],'data')

    def test_immutable_local_review_followup_journal_and_idempotency(self):
        payload=dict(portfolio_id=self.pid,request_id=str(uuid4()),mode='data',question='Podsumuj dane')
        with patch.object(chat,'generate') as generate:
            first=chat.ask(payload);again=chat.ask(payload);generate.assert_not_called()
        self.assertEqual(first,again)
        self.db.execute('UPDATE portfolios SET current_cash=999 WHERE id=?',(self.pid,));self.db.commit()
        follow=dict(payload,request_id=str(uuid4()),question='Dopytanie',session_id=first['id'],expected_last_id=first['messages'][-1]['id'])
        second=chat.ask(follow)
        self.assertEqual(second['snapshot'],first['snapshot']);self.assertEqual(len(second['messages']),2)
        with self.assertRaises(ApiError):chat.ask(dict(follow,request_id=str(uuid4())))
        jid=chat.to_journal(first['messages'][0]['id'])
        self.assertEqual(jid,chat.to_journal(first['messages'][0]['id']))
        self.assertEqual(self.db.execute('SELECT count(*) FROM investor_journal').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM transactions').fetchone()[0],0)

    def test_unknown_ai_sources_rejected(self):
        snap=build(self.pid);answer=facts(snap)
        answer['check']=[dict(text='Invented fact',source_ids=['made-up'])]
        with self.assertRaises(ApiError):chat.validate_answer(answer,snap)

    def test_simulation_conserves_cents_does_not_sell_or_write_finances(self):
        self.holding()
        with self.quotes({'ABC':120}),self.stamps():
            saved=allocation.save_plan(self.pid,dict(version=0,goal='Emerytura',mode='INSTRUMENT',targets=[dict(key='ABC',percent=50),dict(key='CASH',percent=50)]))
            simulation=allocation.simulate(self.pid,dict(contribution=100.01))
            self.assertEqual(saved['version'],1)
            self.assertAlmostEqual(sum(r['contribution'] for r in simulation['rows']),100.01)
            self.assertEqual(simulation['total'],390.01)
            self.assertTrue(all(r['contribution']>=0 for r in simulation['rows']))
            self.assertEqual(next(r for r in simulation['rows'] if r['key']=='ABC')['contribution'],0)
            with self.assertRaises(ApiError):allocation.save_plan(self.pid,dict(saved['plan'],version=0))
        self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios WHERE id=?',(self.pid,)).fetchone()[0],50)
        self.assertEqual(self.db.execute('SELECT count(*) FROM transactions').fetchone()[0],0)
        with self.quotes({}),self.assertRaises(ValidationError):allocation.simulate(self.pid,dict(contribution=100))

    def test_partial_etf_overlap_and_source_dates(self):
        holdings=[dict(ticker='ETFTEST',quantity=1,current_value=100,company_name='Test ETF'),dict(ticker='ABC',quantity=1,current_value=100)]
        exposure.save_composition('ETFTEST',dict(source_url='https://example.org/factsheet',source_date='2025-01-01',constituents=[dict(ticker='ABC',percent=40)]))
        with patch.object(exposure.Value,'get_holdings',return_value=holdings):result=exposure.exposure(self.pid)
        self.assertEqual(result['coverage_percent'],70);self.assertEqual(result['unknown_value'],60)
        self.assertEqual(result['items'][0]['value'],140);self.assertTrue(result['items'][0]['overlap'])
        self.assertTrue(result['funds'][0]['stale'])
        with self.assertRaises(ValidationError):exposure.save_composition('ETFTEST',dict(source_url='https://example.org',source_date=date.today().isoformat(),constituents=[dict(ticker='ABC',percent=101)]))

    def test_provider_budget_idempotency_and_failed_request_no_retry(self):
        from google import genai
        client=MagicMock();client.__enter__.return_value=client
        client.models.count_tokens.return_value=SimpleNamespace(total_tokens=1000)
        client.models.generate_content.return_value=SimpleNamespace(text='{"ok":true}',usage_metadata=SimpleNamespace(prompt_token_count=1000,candidates_token_count=100,thoughts_token_count=0))
        rid=str(uuid4())
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test-key'}),patch.object(genai,'Client',return_value=client):
            args=(rid,'test','input',{},'system')
            self.assertEqual(provider.generate(*args),{'ok':True});self.assertEqual(provider.generate(*args),{'ok':True})
            self.assertEqual(client.models.generate_content.call_count,1)
            with self.assertRaises(ApiError):provider.generate(rid,'test','changed',{},'system')
            cfg=provider.settings();provider.save_settings(dict(cfg,daily_budget_usd=0))
            with self.assertRaises(ApiError):provider.generate(str(uuid4()),'test','input',{},'system')
            self.assertEqual(client.models.generate_content.call_count,1)
            cfg=provider.settings();provider.save_settings(dict(cfg,daily_budget_usd=1))
            client.models.generate_content.side_effect=RuntimeError('provider error')
            failed=str(uuid4())
            with self.assertRaises(ApiError):provider.generate(failed,'test','input',{},'system')
            with self.assertRaises(ApiError):provider.generate(failed,'test','input',{},'system')
            self.assertEqual(client.models.generate_content.call_count,2)
        row=self.db.execute('SELECT state,cost_usd FROM investment_ai_runs WHERE id=?',(failed,)).fetchone()
        self.assertEqual(row['state'],'failed');self.assertGreater(row['cost_usd'],0)

    def test_material_draft_is_not_an_opinion_until_confirmation(self):
        pid=ideas.add_publication(dict(source_id='inwestomat',url='https://inwestomat.eu/test/',title='Test artykułu',published_on=date.today().isoformat()))['id']
        quote='Autor obserwuje ABC i nie deklaruje żadnej transakcji.'
        draft=dict(summary='Omówienie',claims=[dict(ticker='ABC',company='ABC',opinion='WATCH',evidence=quote,seconds=-1,thesis='Obserwacja',risks='Nie podano',horizon='Nie podano')])
        with patch.object(materials,'generate',return_value=draft):
            rows=materials.analyze(pid,dict(request_id=str(uuid4()),input_kind='TRANSCRIPT',text=quote))
        self.assertEqual(self.db.execute('SELECT count(*) FROM research_ideas').fetchone()[0],0)
        claim=rows[0]['result']['claims'][0];self.assertTrue(claim['matched_excerpt'])
        with self.assertRaises(ValidationError):materials.confirm(rows[0]['id'],0,claim)
        saved=materials.confirm(rows[0]['id'],0,dict(claim,confirmed=True))
        self.assertEqual(saved,materials.confirm(rows[0]['id'],0,dict(claim,confirmed=True)))
        self.assertEqual(self.db.execute('SELECT count(*) FROM research_ideas').fetchone()[0],1)

    def test_article_fetch_safe_extract_and_preserves_cache_on_failure(self):
        import investment_article_service as articles
        pid=ideas.add_publication(dict(source_id='inwestomat',url='https://inwestomat.eu/test/',title='Test',published_on=date.today().isoformat()))['id']
        response=MagicMock();response.__enter__.return_value=response;response.status_code=200;response.headers={'Content-Type':'text/html'}
        response.iter_content.return_value=[('<nav>MENU</nav><article class="entry-content"><script>SECRET</script><p>'+('Treść o strategii. '*60)+'</p></article>').encode()]
        with patch.object(articles.requests,'get',return_value=response) as get:result=articles.fetch(pid)
        self.assertNotIn('MENU',result['text']);self.assertNotIn('SECRET',result['text']);self.assertFalse(get.call_args.kwargs['allow_redirects'])
        response.status_code=302
        with patch.object(articles.requests,'get',return_value=response),self.assertRaises(ApiError):articles.fetch(pid)
        self.assertEqual(articles.saved(pid),result)
        with self.assertRaises(ValidationError):materials.analyze(pid,dict(request_id=str(uuid4()),input_kind='ARTICLE',captured_at='old'))

if __name__=='__main__':unittest.main()

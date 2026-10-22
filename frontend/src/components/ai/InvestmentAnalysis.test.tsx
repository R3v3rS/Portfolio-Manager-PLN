import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {MemoryRouter} from 'react-router-dom';
import {investmentAnalysisApi as api,type AnalysisSnapshot,type AnalysisSession} from '../../api_investment_analysis';
import InvestmentAssistant from './InvestmentAssistant';
import StrategyPlan from './StrategyPlan';
import FundExposure from './FundExposure';
import MaterialAnalysis from './MaterialAnalysis';
import type {Publication} from '../../api_ideas';
vi.mock('../../api_investment_analysis',()=>({investmentAnalysisApi:{context:vi.fn(),sessions:vi.fn(),session:vi.fn(),ask:vi.fn(),journal:vi.fn(),settings:vi.fn(),saveSettings:vi.fn(),plan:vi.fn(),savePlan:vi.fn(),simulate:vi.fn(),exposure:vi.fn(),refreshFund:vi.fn(),saveFund:vi.fn(),reviews:vi.fn(),analyzeMaterial:vi.fn(),confirmMaterial:vi.fn(),article:vi.fn(),fetchArticle:vi.fn()}}));
const snapshot={portfolio_id:1,name:'IKE',account_type:'IKE',include_subportfolios:false,created_at:'2026-10-10T12:00:00Z',start:'2026-10-01',end:'2026-10-10',value:{asset_value:1000},results:{profit:40,net_deposits:100},positions:[],warnings:['Brak ceny ABC'],sources:[{id:'results',label:'Wyniki okresu',href:'/portfolio/1?tab=results',data:{profit:40}}]} as AnalysisSnapshot;
const session={id:'session-1',portfolio_id:1,title:'Przegląd',created_at:snapshot.created_at,snapshot,messages:[{id:'message-1',question:'Podsumuj',created_at:snapshot.created_at,journal_id:null,answer:{title:'Analiza',mode:'data',changed:[{text:'Wynik 40 PLN',source_ids:['results']}],why:[],check:[],limitations:[]}}]} as AnalysisSession;
beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.sessions).mockResolvedValue([]);vi.mocked(api.context).mockResolvedValue(snapshot);vi.mocked(api.settings).mockResolvedValue({configured:false,used_usd:0,daily_budget_usd:.25,model:'gemini-3.1-flash-lite',input_usd_per_million:.25,output_usd_per_million:1.5,max_output_tokens:4096,version:0,budget_day:'2026-10-10',price_note:'Szacowanie'});vi.mocked(api.ask).mockResolvedValue(session);vi.mocked(api.journal).mockResolvedValue({id:9});});
afterEach(cleanup);
describe('Investment analysis workflows',()=>{
 it('does not send data to AI on opening; saves local review and journal once',async()=>{
  render(<MemoryRouter><InvestmentAssistant portfolioId={1}/></MemoryRouter>);
  await screen.findByText('Brak ceny ABC');expect(api.ask).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Zapisz podsumowanie danych'}));
  await screen.findByText('Wynik 40 PLN');expect(api.ask).toHaveBeenCalledWith(expect.objectContaining({mode:'data'}));
  expect(screen.getByText(/Dopytania korzystają z tego samego stanu/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Zapisz w dzienniku'}));await screen.findByRole('link',{name:'Zapisano w dzienniku'});
  expect(api.journal).toHaveBeenCalledTimes(1);
 });
 it('keeps the question and request ID on retry, followups reference the saved snapshot',async()=>{
  vi.mocked(api.ask).mockRejectedValueOnce(new Error('Błąd sieci'));
  render(<MemoryRouter><InvestmentAssistant portfolioId={1}/></MemoryRouter>);await screen.findByText('Brak ceny ABC');
  fireEvent.change(screen.getByLabelText('Twoje pytanie'),{target:{value:'Dlaczego wynik się zmienił?'}});
  fireEvent.click(screen.getByRole('button',{name:'Analizuj z AI'}));await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button',{name:'Analizuj z AI'}));await screen.findByText('Wynik 40 PLN');
  expect(vi.mocked(api.ask).mock.calls[0][0].request_id).toBe(vi.mocked(api.ask).mock.calls[1][0].request_id);
  fireEvent.change(screen.getByLabelText('Twoje pytanie'),{target:{value:'A wpłaty?'}});fireEvent.click(screen.getByRole('button',{name:'Analizuj z AI'}));
  await waitFor(()=>expect(api.ask).toHaveBeenLastCalledWith(expect.objectContaining({session_id:'session-1',expected_last_id:'message-1'})));
 });
 it('requires saved target weights before using contribution simulation',async()=>{
  const plan={goal:'Emerytura',horizon:'10 lat',constraints:'',mode:'INSTRUMENT' as const,targets:[{key:'ABC',percent:100}]};
  vi.mocked(api.plan).mockResolvedValue({plan,version:1,portfolio_id:1,archived:false,instruments:['ABC'],children:[],account_type:'IKE'});
  render(<StrategyPlan portfolioId={1}/>);await screen.findByDisplayValue('Emerytura');
  fireEvent.change(screen.getByLabelText('Udział 1'),{target:{value:'80'}});
  expect(screen.getByRole('button',{name:'Zapisz założenia'})).toBeDisabled();expect(screen.getByRole('button',{name:'Oblicz podział'})).toBeDisabled();expect(api.simulate).not.toHaveBeenCalled();
 });
 it('shows unknown ETF coverage and filters overlap',async()=>{
  vi.mocked(api.exposure).mockResolvedValue({coverage_percent:40,unknown_value:600,warnings:[],funds:[],items:[{ticker:'ABC',value:400,weight_percent:40,overlap:false,sources:[]}]});
  render(<FundExposure portfolioId={1}/>);await screen.findByText('40.0%');expect(screen.getByText('Nieznany skład')).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText(/Tylko spółki/));expect(screen.queryByRole('rowheader',{name:'ABC'})).not.toBeInTheDocument();
 });
 it('requires article preview and explicit confirmation before saving extracted claims',async()=>{
  const publication={id:7,url:'https://inwestomat.eu/test/',title:'Strategia ETF'} as Publication;
  const claim={ticker:'ABC',company:'ABC',opinion:'WATCH',evidence:'Autor obserwuje ABC',thesis:'Wzrost',risks:'Nie podano',horizon:'Nie podano',seconds:null,matched_excerpt:true,status:'needs_review',source_url:publication.url};
  vi.mocked(api.article).mockResolvedValue(null);vi.mocked(api.reviews).mockResolvedValue([]);vi.mocked(api.fetchArticle).mockResolvedValue({text:'Treść źródłowa',source_url:publication.url,captured_at:'2026-10-10',truncated:false});
  vi.mocked(api.analyzeMaterial).mockResolvedValue([{id:'review-1',publication_id:7,input_kind:'ARTICLE',created_at:'2026-10-10',result:{summary:'Streszczenie',claims:[claim]},confirmed:{}}]);
  vi.mocked(api.confirmMaterial).mockResolvedValue({id:1});
  render(<MaterialAnalysis publication={publication} onClose={()=>{}} onSaved={()=>{}}/>);
  expect(screen.getByRole('button',{name:'Przygotuj szkic AI'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'Pobierz treść artykułu'}));await screen.findByText('Treść źródłowa');
  fireEvent.click(screen.getByRole('button',{name:'Przygotuj szkic AI'}));await screen.findByText('Streszczenie');
  expect(api.confirmMaterial).not.toHaveBeenCalled();expect(screen.getByRole('button',{name:'Potwierdź i zapisz analizę'})).toBeDisabled();
  fireEvent.click(screen.getByLabelText(/Sprawdziłem źródło/));fireEvent.click(screen.getByRole('button',{name:'Potwierdź i zapisz analizę'}));
  await waitFor(()=>expect(api.confirmMaterial).toHaveBeenCalledWith('review-1',0,expect.objectContaining({confirmed:true,ticker:'ABC'})));
 });
});

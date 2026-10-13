import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {MemoryRouter} from 'react-router-dom';
import InvestmentIdeas from './InvestmentIdeas';
import {ideasApi,type ResearchWorkspace} from '../api_ideas';

vi.mock('../api_ideas',()=>({ideasApi:{workspace:vi.fn(),refresh:vi.fn(),publication:vi.fn(),save:vi.fn()}}));
vi.mock('../api_radar',()=>({radarApi:{addToWatchlist:vi.fn()}}));
const data:ResearchWorkspace={sources:[{id:'podlacki',name:'Marcin Podlacki',kind:'youtube',url:'https://www.youtube.com/@MarcinPodlacki',checked_at:null,status:'never',message:''},{id:'zawod',name:'Zawód Inwestor',kind:'youtube',url:'https://www.youtube.com/@zawodinwestor',checked_at:null,status:'unavailable',message:'Niedostępne'}],
  publications:[{id:1,source_id:'podlacki',url:'https://www.youtube.com/watch?v=abcdefghijk',title:'Pomysły na miesiąc',published_on:'2026-10-01',excerpt:'Opis, nie decyzja zakupu',publisher:'Marcin Podlacki',provenance:'FEED',suggestions:['PZU.WA'],captured_at:'2026-10-10'}],
  ideas:[],months:['2026-10'],instruments:[{ticker:'PZU.WA',company_name:'PZU'}],as_of:'2026-10-10'};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(ideasApi.workspace).mockResolvedValue(data);vi.mocked(ideasApi.refresh).mockResolvedValue({sources:[]});vi.mocked(ideasApi.save).mockResolvedValue({id:1});vi.mocked(ideasApi.publication).mockResolvedValue({id:1});Element.prototype.scrollIntoView=vi.fn();});
afterEach(cleanup);
const mount=()=>render(<MemoryRouter><InvestmentIdeas/></MemoryRouter>);
describe('Investment research workflow',()=>{
  it('loads cached materials without network refresh and exposes unavailable source',async()=>{
    mount();expect(await screen.findByRole('link',{name:/Pomysły na miesiąc/})).toBeInTheDocument();
    expect(ideasApi.refresh).not.toHaveBeenCalled();expect(screen.getByText('Niedostępne')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Odśwież publikacje'}));
    expect(await screen.findByText(/Sprawdzono źródła/)).toBeInTheDocument();expect(ideasApi.refresh).toHaveBeenCalledTimes(1);
  });
  it('treats suggested ticker as a mention and saves own analysis with evidence',async()=>{
    mount();fireEvent.click(await screen.findByRole('button',{name:'PZU.WA'}));
    const form=screen.getByRole('form',{name:'Twoja analiza spółki'});
    expect(within(form).getByLabelText(/Opinia autora/)).toHaveValue('MENTION');
    fireEvent.change(within(form).getByLabelText(/Opinia autora/),{target:{value:'HOLD'}});
    expect(within(form).getByLabelText(/Potwierdzenie opinii/)).toBeRequired();
    fireEvent.change(within(form).getByLabelText(/Potwierdzenie opinii/),{target:{value:'12:00 deklaruje posiadanie'}});
    fireEvent.change(within(form).getByLabelText('Ryzyka i co chcę sprawdzić'),{target:{value:'Sprawdzić zadłużenie'}});
    fireEvent.click(within(form).getByRole('button',{name:'Zapisz analizę'}));
    await screen.findByText(/Zapisano Twoją analizę/);
    expect(ideasApi.save).toHaveBeenCalledWith(expect.objectContaining({ticker:'PZU.WA',opinion:'HOLD',evidence:'12:00 deklaruje posiadanie',risks:'Sprawdzić zadłużenie'}),undefined);
  });
  it('filters source and month and keeps older materials reachable',async()=>{
    mount();await screen.findByRole('link',{name:/Pomysły na miesiąc/});
    fireEvent.change(screen.getByRole('combobox',{name:'Filtr źródła'}),{target:{value:'zawod'}});
    expect(screen.queryByRole('link',{name:/Pomysły na miesiąc/})).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole('combobox',{name:'Miesiąc publikacji'}),{target:{value:''}});
    await screen.findByText('Brak materiałów w tym widoku');expect(ideasApi.workspace).toHaveBeenLastCalledWith('');
  });
  it('preserves draft after save failure and can retry',async()=>{
    vi.mocked(ideasApi.save).mockRejectedValueOnce(new Error('Zapis niedostępny'));
    mount();fireEvent.click(await screen.findByRole('button',{name:'PZU.WA'}));
    fireEvent.change(screen.getByLabelText('Moje argumenty za'),{target:{value:'Moja teza'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz analizę'}));
    await screen.findByRole('alert');expect(screen.getByLabelText('Moje argumenty za')).toHaveValue('Moja teza');
    fireEvent.click(screen.getByRole('button',{name:'Zapisz analizę'}));await screen.findByText(/Zapisano Twoją analizę/);
    expect(ideasApi.save).toHaveBeenCalledTimes(2);
  });
});

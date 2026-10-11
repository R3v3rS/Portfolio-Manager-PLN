import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import InvestorJournal from './InvestorJournal';
import { journalApi, type JournalDetail, type JournalWorkspace } from '../api_journal';

vi.mock('../api_journal',()=>({journalApi:{list:vi.fn(),detail:vi.fn(),create:vi.fn(),update:vi.fn(),archive:vi.fn(),review:vi.fn(),export:vi.fn()}}));
const entry:JournalDetail={id:1,title:'Dlaczego kupuję ETF',entry_date:'2025-01-01',kind:'BUY',status:'ACTIVE',ticker:'CSPX.L',portfolio_id:1,confidence:4,thesis:'Wzrost w długim terminie',risks:'Wahania rynku',invalidation:'Zmiana strategii',exit_plan:'Przegląd przed zmianą',review_date:'2026-01-01',tags:['ETF'],version:1,is_archived:false,created_at:'2025-01-01',updated_at:'2025-01-01',portfolio_name:'IKE',portfolio_archived:false,review_count:0,review_due:true,reviews:[],revisions:[]};
const empty:JournalWorkspace={entries:[],total:0,page:1,page_size:50,stats:{active:0,watching:0,closed:0,due:0,archived:0},portfolios:[{id:1,name:'IKE',is_archived:false}],tags:[],as_of:'2026-10-02'};
const filled:JournalWorkspace={...empty,entries:[entry],total:1,stats:{...empty.stats,active:1,due:1},tags:['ETF']};
const show=(path='/journal')=>render(<MemoryRouter initialEntries={[path]}><InvestorJournal/></MemoryRouter>);
beforeEach(()=>{vi.clearAllMocks();vi.mocked(journalApi.list).mockResolvedValue(filled);vi.mocked(journalApi.detail).mockResolvedValue(entry);vi.mocked(journalApi.create).mockResolvedValue({id:1});vi.mocked(journalApi.update).mockResolvedValue({id:1});vi.mocked(journalApi.archive).mockResolvedValue({id:1});vi.mocked(journalApi.review).mockResolvedValue({id:2,entry_id:1});});
afterEach(cleanup);

describe('Investor journal workflow',()=>{
  it('creates a decision from portfolio and ticker context, then loads its saved detail',async()=>{
    vi.mocked(journalApi.list).mockResolvedValue(empty);
    show('/journal?new=1&portfolio=1&ticker=cspx.l');
    const form=await screen.findByRole('form',{name:'Nowy wpis dziennika'});
    expect(within(form).getByLabelText('Portfel')).toHaveValue('1');expect(within(form).getByLabelText('Symbol instrumentu')).toHaveValue('CSPX.L');
    fireEvent.change(within(form).getByLabelText('Tytuł wpisu'),{target:{value:entry.title}});
    fireEvent.change(within(form).getByLabelText('Teza i powód decyzji'),{target:{value:entry.thesis}});
    fireEvent.change(within(form).getByLabelText('Etykiety'),{target:{value:'ETF, Emerytura'}});
    vi.mocked(journalApi.list).mockResolvedValue(filled);
    fireEvent.click(within(form).getByRole('button',{name:'Zapisz wpis'}));
    await waitFor(()=>expect(journalApi.create).toHaveBeenCalledWith(expect.objectContaining({title:entry.title,thesis:entry.thesis,ticker:'CSPX.L',portfolio_id:1,tags:['ETF','Emerytura']})));
    expect(await screen.findByRole('button',{name:'Dodaj przegląd'})).toBeInTheDocument();
    expect(screen.queryByRole('form',{name:'Nowy wpis dziennika'})).not.toBeInTheDocument();
  });
  it('does not create a second entry when reading the list fails after a successful save',async()=>{
    vi.mocked(journalApi.list).mockResolvedValueOnce(empty).mockRejectedValueOnce(new Error('Odczyt niedostępny')).mockResolvedValue(filled);
    show('/journal?new=1');
    fireEvent.change(await screen.findByLabelText('Tytuł wpisu'),{target:{value:entry.title}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz wpis'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Odczyt niedostępny');
    expect(screen.queryByRole('button',{name:'Zapisz wpis'})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Wczytaj ponownie'}));
    await waitFor(()=>expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    expect(journalApi.create).toHaveBeenCalledTimes(1);
  });
  it('keeps unsaved edits on a version conflict and sends the original version',async()=>{
    vi.mocked(journalApi.update).mockRejectedValue(new Error('Wpis został już zmieniony'));
    show();fireEvent.click(await screen.findByRole('button',{name:'Edytuj'}));
    fireEvent.change(screen.getByLabelText('Teza i powód decyzji'),{target:{value:'Moja nowa teza'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz zmiany'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Wpis został już zmieniony');
    expect(screen.getByLabelText('Teza i powód decyzji')).toHaveValue('Moja nowa teza');
    expect(journalApi.update).toHaveBeenCalledWith(1,expect.objectContaining({thesis:'Moja nowa teza'}),1);
  });
  it('appends a review with lessons without overwriting the investment thesis',async()=>{
    show();fireEvent.click(await screen.findByRole('button',{name:'Dodaj przegląd'}));
    expect(screen.getByText(entry.thesis)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Co się zmieniło i co robię dalej?'),{target:{value:'Nowe wyniki potwierdzają założenia'}});
    fireEvent.change(screen.getByLabelText('Wnioski na przyszłość'),{target:{value:'Zachować regularność'}});
    fireEvent.change(screen.getByLabelText('Ocena tezy'),{target:{value:'CONFIRMED'}});
    const reviewed:JournalDetail={...entry,version:2,review_date:null,review_due:false,review_count:1,reviews:[{id:2,entry_id:1,review_date:'2026-10-02',outcome:'CONFIRMED',notes:'Nowe wyniki potwierdzają założenia',lessons:'Zachować regularność',entry_status:'ACTIVE',next_review_date:null,created_at:'2026-10-02'}]};
    vi.mocked(journalApi.detail).mockResolvedValue(reviewed);
    fireEvent.click(screen.getByRole('button',{name:'Zapisz przegląd'}));
    await waitFor(()=>expect(screen.queryByRole('form',{name:'Przegląd decyzji'})).not.toBeInTheDocument());
    expect(await screen.findByText('Zachować regularność')).toBeInTheDocument();
    expect(journalApi.review).toHaveBeenCalledWith(1,expect.objectContaining({version:1,notes:'Nowe wyniki potwierdzają założenia',next_review_date:null}));
    expect(journalApi.update).not.toHaveBeenCalled();expect(screen.getByText(entry.thesis)).toBeInTheDocument();
  });
  it('archives and restores a note while preserving its detail',async()=>{
    show();const archived={...entry,is_archived:true,version:2,review_due:false};
    await screen.findByRole('button',{name:'Archiwizuj wpis'});
    vi.mocked(journalApi.detail).mockResolvedValue(archived);vi.mocked(journalApi.list).mockResolvedValue({...filled,entries:[archived],stats:{...empty.stats,archived:1}});
    fireEvent.click(screen.getByRole('button',{name:'Archiwizuj wpis'}));
    const restore=await screen.findByRole('button',{name:'Przywróć wpis'});
    expect(journalApi.archive).toHaveBeenCalledWith(1,true,1);
    vi.mocked(journalApi.detail).mockResolvedValue({...entry,version:3});vi.mocked(journalApi.list).mockResolvedValue(filled);
    fireEvent.click(restore);await screen.findByRole('button',{name:'Archiwizuj wpis'});
    expect(journalApi.archive).toHaveBeenLastCalledWith(1,false,2);
  });
  it('filters due reviews and searches Unicode text',async()=>{
    show();await screen.findByRole('button',{name:'Dodaj przegląd'});
    fireEvent.click(screen.getByRole('button',{name:/Przegląd na dziś lub zaległy/}));
    await waitFor(()=>expect(journalApi.list).toHaveBeenLastCalledWith(expect.objectContaining({due:'1',page:1})));
    fireEvent.change(screen.getByLabelText('Szukaj w dzienniku'),{target:{value:'ŻÓŁTA'}});
    await waitFor(()=>expect(journalApi.list).toHaveBeenLastCalledWith(expect.objectContaining({q:'ŻÓŁTA'})));
    fireEvent.click(screen.getByRole('button',{name:'Wyczyść filtry'}));
    await waitFor(()=>expect(journalApi.list).toHaveBeenLastCalledWith(expect.objectContaining({due:'0',q:'',ticker:''})));
  });
  it('shows previous reasoning in the revision history',async()=>{
    vi.mocked(journalApi.detail).mockResolvedValue({...entry,version:2,thesis:'Nowa teza',revisions:[{version:1,reason:'create',created_at:'2025-01-01',snapshot:entry}]});
    show();await screen.findByRole('button',{name:'Dodaj przegląd'});
    fireEvent.click(screen.getByText(/Historia zmian wpisu/));fireEvent.click(screen.getByText(/Wersja 1 · Pierwszy zapis/));
    expect(screen.getByText('Wzrost w długim terminie')).toBeInTheDocument();expect(screen.getByText('Nowa teza')).toBeInTheDocument();
  });
});

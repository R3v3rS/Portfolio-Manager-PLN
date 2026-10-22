import {fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {beforeEach,expect,it,vi} from 'vitest';
import BudgetReserves from '../../pages/BudgetReserves';
import {reservesApi,type ReserveSummary,type ReservesWorkspace,type Reserve} from '../../api_reserves';
import {ReserveMonthlyStatement,ReserveJournal} from './ReserveActivity';
import ReserveBatchFunding from './ReserveBatchFunding';

vi.mock('../../api_reserves',()=>({reservesApi:{get:vi.fn(),preview:vi.fn(),move:vi.fn(),fundingPlan:vi.fn(),fundingPreview:vi.fn(),fundBatch:vi.fn(),archive:vi.fn()}}));
const account={id:2,name:'Alior',balance:900,reserved:382,available:518};
const summary:ReserveSummary={kind:'SPEND',date:'2026-10-19',reserve_id:4,reserve_name:'Woda kwartał',amount:374.2,
  reserve_before:382,reserve_after:0,covered:374.2,released:382,surplus:7.8,surplus_mode:'FREE',surplus_reserve_name:null,available_change:7.8,budget_entry_id:76,
  accounts:[{account_id:2,account_name:'Alior',balance_before:900,balance_after:525.8,reserved_before:382,reserved_after:0,available_before:518,available_after:525.8}]};
const reserve:Reserve={id:4,name:'Woda kwartał',notes:'',account_id:2,account_name:'Alior',target_amount:382,saved:382,start_date:'2026-10-01',due_date:'2026-10-30',frequency:'ONCE',cycle:1,version:3,status:'ACTIVE',remaining:0,monthly_required:0,months_left:0,next_contribution_date:null,progress_percent:100,surplus:0,urgent:false,overdue:false,funded_this_month:true,movements:[]};
const context=():ReservesWorkspace=>({month:'2026-10',as_of:'2026-10-19',accounts:[account],categories:[{id:21,name:'Woda'}],items:[{...reserve}],warnings:[],totals:{saved:382,remaining:0,monthly_required:0,urgent_amount:0,active:1}});
const show=(children:React.ReactNode,path='/budget/reserves?month=2026-10')=>render(<MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>);
beforeEach(()=>{vi.resetAllMocks();vi.mocked(reservesApi.get).mockResolvedValue(context());vi.mocked(reservesApi.preview).mockResolvedValue({...summary,expected_state:'snapshot'});vi.mocked(reservesApi.move).mockResolvedValue({id:6,budget_entry_id:76,summary});});

it('previews before payment, invalidates it after an edit and saves the exact snapshot once',async()=>{
  show(<BudgetReserves/>);fireEvent.click(await screen.findByRole('button',{name:'Zapisz płatność'}));
  fireEvent.change(screen.getByLabelText('Zapłacona kwota w PLN'),{target:{value:'374.2'}});
  fireEvent.click(screen.getByRole('button',{name:'Sprawdź podgląd'}));
  const preview=await screen.findByRole('region',{name:'Podgląd przed zapisem'});
  expect(preview).toHaveTextContent(/7,80/);expect(reservesApi.move).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Zapłacona kwota w PLN'),{target:{value:'374'}});
  expect(screen.queryByRole('region',{name:'Podgląd przed zapisem'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Sprawdź podgląd'}));await screen.findByRole('region',{name:'Podgląd przed zapisem'});
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Zapisz płatność'}));
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(reservesApi.move).toHaveBeenCalledWith(4,expect.objectContaining({amount:374,expected_state:'snapshot',surplus_mode:'FREE'}),3,expect.any(String));
  expect(screen.getByRole('link',{name:'Pokaż transakcję'})).toHaveAttribute('href','/budget?view=entries&month=2026-10&entry_id=76');
});

it('opens a completed reserve directly and shows the released water surplus',async()=>{
  const data=context();data.items=[{...reserve,status:'COMPLETED',saved:0,journal:[{id:'m:6',kind:'SPEND',title:'Rozliczenie płatności',date:'2026-10-19',amount:374.2,reserve_change:-382,bank_change:-374.2,account_name:'Alior',notes:'',transfer:null,budget_entry_id:76,summary}]}];
  vi.mocked(reservesApi.get).mockResolvedValue(data);show(<BudgetReserves/>,'/budget/reserves?month=2026-10&reserve=4');
  const history=await screen.findByText('Historia rezerwy (1)');
  expect(history.closest('details')).toHaveAttribute('open');
  expect(screen.getByText(/Do wolnych środków wróciło/)).toHaveTextContent('7,80');
  expect(screen.getByRole('button',{name:'Rozliczone i archiwum'})).toHaveAttribute('aria-pressed','true');
});

it('keeps the monthly statement balanced and changes its month without recording money',()=>{
  const change=vi.fn();const item={...reserve,month_statement:{month:'2026-10',opening:242,added:140,used:374.2,released:7.8,payments:374.2,ending:0,planned:140,funded:140,remaining:0}};
  show(<ReserveMonthlyStatement items={[item]} month="2026-10" onMonth={change}/>);
  fireEvent.click(screen.getByText('Zestawienie miesięczne rezerw'));
  const table=screen.getByRole('table');expect(table).toHaveTextContent('374,20');expect(table).toHaveTextContent('7,80');expect(table).toHaveTextContent('Plan: 140,00');
  fireEvent.change(screen.getByLabelText('Miesiąc zestawienia'),{target:{value:'2026-11'}});expect(change).toHaveBeenCalledWith('2026-11');expect(reservesApi.move).not.toHaveBeenCalled();
});

it('combines bank transfer and funding and filters the same journal',()=>{
  const item={...reserve,journal:[{id:'m:2',kind:'FUND' as const,title:'Przelew i odłożenie',date:'2026-10-08',amount:140,reserve_change:140,bank_change:0,account_name:'Alior',notes:'',transfer:{source:'PKO',target:'Alior'},budget_entry_id:null,summary:null}]};
  show(<ReserveJournal item={item} month="2026-10" open onUndo={vi.fn()}/>);
  expect(screen.getByText('Przelew i odłożenie')).toBeInTheDocument();expect(screen.getByText(/PKO → Alior/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Operacje'),{target:{value:'SPEND'}});expect(screen.queryByText('Przelew i odłożenie')).not.toBeInTheDocument();
  expect(screen.getByText('Brak operacji dla wybranych filtrów.')).toBeInTheDocument();
});

it('sends the selected surplus destination with its version and never creates another payment in preview',async()=>{
  const data=context();data.items.push({...reserve,id:8,name:'Serwis auta',saved:0,version:5});vi.mocked(reservesApi.get).mockResolvedValue(data);
  show(<BudgetReserves/>);const card=(await screen.findByRole('heading',{name:'Woda kwartał'})).closest('article')!;
  fireEvent.click(within(card).getByRole('button',{name:'Zapisz płatność'}));fireEvent.change(screen.getByLabelText('Zapłacona kwota w PLN'),{target:{value:'374.2'}});
  fireEvent.change(screen.getByLabelText(/Co zrobić z nadwyżką/),{target:{value:'RESERVE'}});fireEvent.change(screen.getByLabelText('Rezerwa dla nadwyżki'),{target:{value:'8'}});
  fireEvent.click(screen.getByRole('button',{name:'Sprawdź podgląd'}));await screen.findByRole('region',{name:'Podgląd przed zapisem'});
  expect(reservesApi.preview).toHaveBeenCalledWith(4,expect.objectContaining({surplus_mode:'RESERVE',surplus_reserve_id:8,surplus_reserve_version:5}),3);
  expect(reservesApi.move).not.toHaveBeenCalled();
});

it('funds several reserves only after preview, allows corrections and preserves retry identity',async()=>{
  const data=context(),saved=vi.fn();
  vi.mocked(reservesApi.fundingPlan).mockResolvedValue({month:'2026-10',date:'2026-10-19',remaining:200,proposed:150,rows:[{reserve_id:4,name:'Woda',account_id:2,priority:1,remaining:100,proposed:100,version:3},{reserve_id:8,name:'OC',account_id:2,priority:3,remaining:100,proposed:50,version:1}]});
  vi.mocked(reservesApi.fundingPreview).mockResolvedValue({expected_state:'bulk-snapshot',accounts:summary.accounts,total:150,rows:[]});
  vi.mocked(reservesApi.fundBatch).mockRejectedValueOnce(new Error('Nie otrzymano potwierdzenia')).mockResolvedValue({expected_state:'bulk-snapshot',accounts:[],total:150,rows:[]});
  show(<ReserveBatchFunding data={data} onClose={vi.fn()} onSaved={saved}/>);
  await screen.findByLabelText('Odłożenie: Woda');expect(screen.getByLabelText('Odłożenie: OC')).toHaveValue(50);
  fireEvent.click(screen.getByRole('button',{name:'Sprawdź podgląd'}));await screen.findByRole('region',{name:'Podgląd zbiorczego odkładania'});expect(reservesApi.fundBatch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Odłożenie: OC'),{target:{value:'40'}});expect(screen.queryByRole('region',{name:'Podgląd zbiorczego odkładania'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Sprawdź podgląd'}));await screen.findByRole('region',{name:'Podgląd zbiorczego odkładania'});
  fireEvent.click(screen.getByRole('button',{name:'Zatwierdź odłożenia'}));await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button',{name:'Zatwierdź odłożenia'}));await waitFor(()=>expect(saved).toHaveBeenCalled());
  const calls=vi.mocked(reservesApi.fundBatch).mock.calls;expect(calls[0][1]).toBe(calls[1][1]);expect(calls[1][0]).toMatchObject({expected_state:'bulk-snapshot',rows:[{reserve_id:4,amount:100},{reserve_id:8,amount:40}]});
});

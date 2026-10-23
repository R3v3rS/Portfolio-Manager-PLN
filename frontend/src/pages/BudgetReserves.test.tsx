import {setBudgetManagement} from '../components/budget/budgetMode';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import BudgetReserves from './BudgetReserves';
import { reservesApi, type Reserve, type ReservesWorkspace } from '../api_reserves';
import { budgetImportsApi } from '../api_budget_imports';

vi.mock('../api_reserves',() => ({reservesApi:{get:vi.fn(),create:vi.fn(),update:vi.fn(),move:vi.fn(),preview:vi.fn(),fundingPlan:vi.fn(),fundingPreview:vi.fn(),fundBatch:vi.fn(),archive:vi.fn()}}));
vi.mock('../api_budget_imports',()=>({budgetImportsApi:{matches:vi.fn()}}));
const reserve:Reserve={id:7,name:'Ubezpieczenie auta',notes:'Polisa roczna',account_id:1,account_name:'Konto',
  target_amount:2400,saved:500,remaining:1900,due_date:'2027-09-30',start_date:'2026-10-02',frequency:'YEARLY',
  cycle:1,version:2,status:'ACTIVE',monthly_required:172.73,months_left:11,next_contribution_date:'2026-11-01',
  progress_percent:20.83,surplus:0,urgent:false,overdue:false,funded_this_month:true,
  movements:[{id:1,cycle:1,kind:'ADD',amount:500,date:'2026-10-02',notes:'Pierwsza kwota',expense_amount:null,budget_entry_id:null}]};
const workspace=():ReservesWorkspace=>({as_of:'2026-10-02',items:[{...reserve}],accounts:[{id:1,name:'Konto',balance:10000,reserved:500,available:9500}],
  categories:[{id:2,name:'Ubezpieczenia'}],warnings:[],totals:{saved:500,remaining:1900,monthly_required:172.73,urgent_amount:0,active:1}});
const show=()=>render(<MemoryRouter initialEntries={['/budget/reserves?reserve=7']}><BudgetReserves/></MemoryRouter>);
const get=vi.mocked(reservesApi.get);
async function review(){fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Sprawdź podgląd'}));await screen.findByRole('region',{name:'Podgląd przed zapisem'});}
beforeEach(()=>{setBudgetManagement(true);vi.resetAllMocks();vi.mocked(reservesApi.preview).mockImplementation(async(id,input)=>({...input,reserve_id:id,reserve_name:reserve.name,covered:0,released:0,surplus:0,surplus_mode:'KEEP',surplus_reserve_name:null,accounts:[],budget_entry_id:null,expected_state:'snapshot'}));get.mockResolvedValue(workspace());vi.mocked(reservesApi.create).mockResolvedValue({id:8});vi.mocked(reservesApi.move).mockResolvedValue({id:2,budget_entry_id:null});});

describe('Budget reserves',()=>{
  it('starts a new monthly pool in the selected month without creating a deposit',async()=>{
    show();await screen.findByRole('heading',{name:reserve.name});
    fireEvent.click(screen.getByRole('button',{name:'Nowa rezerwa'}));
    fireEvent.change(screen.getByLabelText('Sposób planowania'),{target:{value:'MONTHLY'}});
    fireEvent.change(screen.getByLabelText('Nazwa rezerwy'),{target:{value:'Woda Listopad - Styczeń'}});
    fireEvent.change(screen.getByLabelText('Domyślna kwota miesięczna w PLN'),{target:{value:'140'}});
    fireEvent.change(screen.getByLabelText('Kategoria przyszłej płatności'),{target:{value:'2'}});
    fireEvent.change(screen.getByLabelText('Początek odkładania'),{target:{value:'2026-11'}});
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Utwórz rezerwę'}));
    await waitFor(()=>expect(reservesApi.create).toHaveBeenCalledWith(expect.objectContaining({monthly_start_month:'2026-11',monthly_amount:140}),expect.any(String)));
    expect(reservesApi.move).not.toHaveBeenCalled();
  });
  it('shows a future start and links to its first month instead of October',async()=>{
    const data=workspace();data.items=[{...reserve,name:'Woda Listopad - Styczeń',monthly_amount:140,monthly_start_month:'2026-11',monthly_started:false,
      month_planned:0,month_allocated:0,saved:0,remaining:0,monthly_required:0,movements:[]}];get.mockResolvedValue(data);
    show();const card=(await screen.findByRole('heading',{name:'Woda Listopad - Styczeń'})).closest('article')!;
    expect(card).toHaveTextContent('Początek odkładania: listopad 2026');
    expect(card).toHaveTextContent(/Plan bieżącego miesiąca: 0,00/);
    expect(within(card).getByRole('link',{name:'Koryguj pierwszy miesiąc'})).toHaveAttribute('href','/budget?view=plan&month=2026-11');
    expect(within(card).queryByRole('link',{name:'Koryguj bieżący miesiąc'})).not.toBeInTheDocument();
    fireEvent.click(within(card).getByRole('button',{name:'Edytuj rezerwę: Woda Listopad - Styczeń'}));
    expect(screen.getByLabelText('Początek odkładania')).toHaveValue('2026-11');
    expect(screen.getByLabelText('Początek odkładania')).toBeEnabled();
  });
  it('protects the starting month of a monthly reserve with recorded movements',async()=>{
    const data=workspace();data.items=[{...reserve,monthly_amount:140,monthly_start_month:'2026-10'}];get.mockResolvedValue(data);
    show();await screen.findByRole('heading',{name:reserve.name});
    fireEvent.click(screen.getByRole('button',{name:`Edytuj rezerwę: ${reserve.name}`}));
    expect(screen.getByLabelText('Początek odkładania')).toBeDisabled();
    expect(screen.getByText(/Pula ma historię odłożeń lub rozliczeń/)).toBeInTheDocument();
  });
  it('creates a reserve without deadline with a fixed zero plan and optional category',async()=>{
    show();await screen.findByRole('heading',{name:reserve.name});
    fireEvent.click(screen.getByRole('button',{name:'Nowa rezerwa'}));
    fireEvent.change(screen.getByLabelText('Sposób planowania'),{target:{value:'OPEN'}});
    fireEvent.change(screen.getByLabelText('Nazwa rezerwy'),{target:{value:'Poduszka'}});
    expect(screen.getByLabelText('Domyślna kwota miesięczna w PLN')).toHaveValue(0);
    expect(screen.queryByLabelText('Termin wydatku')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Przewidywany koszt w PLN')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Kategoria przyszłej płatności')).not.toBeRequired();
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Utwórz rezerwę'}));
    await waitFor(()=>expect(reservesApi.create).toHaveBeenCalledWith(expect.objectContaining({name:'Poduszka',open_ended:true,monthly_amount:0,category_id:null}),expect.any(String)));
    expect(reservesApi.move).not.toHaveBeenCalled();
  });
  it('shows an open reserve as fixed saving rather than a target or media pool',async()=>{
    const data=workspace();data.items=[{...reserve,open_ended:true,monthly_amount:0,month_planned:0,month_allocated:333,saved:333,remaining:0,monthly_required:0}];get.mockResolvedValue(data);
    show();const card=(await screen.findByRole('heading',{name:reserve.name})).closest('article')!;
    expect(card).toHaveTextContent('Bez terminu');
    expect(card).toHaveTextContent('Brak obowiązkowej wpłaty');
    expect(within(card).queryByRole('progressbar')).not.toBeInTheDocument();
    expect(within(card).queryByRole('link',{name:'Koryguj bieżący miesiąc'})).not.toBeInTheDocument();
    expect(within(card).getByRole('button',{name:'Odłóż środki'})).toBeEnabled();
  });
  it('creates a monthly media pool without requiring a deadline',async()=>{
    show();await screen.findByRole('heading',{name:reserve.name});
    fireEvent.click(screen.getByRole('button',{name:'Nowa rezerwa'}));
    fireEvent.change(screen.getByLabelText('Sposób planowania'),{target:{value:'MONTHLY'}});
    fireEvent.change(screen.getByLabelText('Nazwa rezerwy'),{target:{value:'Prąd'}});
    fireEvent.change(screen.getByLabelText('Domyślna kwota miesięczna w PLN'),{target:{value:'250'}});
    fireEvent.change(screen.getByLabelText('Kategoria przyszłej płatności'),{target:{value:'2'}});
    expect(screen.queryByLabelText('Termin wydatku')).not.toBeInTheDocument();
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Utwórz rezerwę'}));
    await waitFor(()=>expect(reservesApi.create).toHaveBeenCalledWith(expect.objectContaining({name:'Prąd',monthly_amount:250,category_id:2}),expect.any(String)));
    expect(reservesApi.move).not.toHaveBeenCalled();
  });
  it('shows a continuous media reserve and keeps savings after the bill',async()=>{
    const data=workspace();data.items=[{...reserve,name:'Prąd',monthly_amount:250,month_planned:220,month_allocated:220,saved:70,remaining:0,monthly_required:0}];get.mockResolvedValue(data);
    show();const card=(await screen.findByRole('heading',{name:'Prąd'})).closest('article')!;
    expect(card).toHaveTextContent('Miesięczna pula na media');
    expect(card).toHaveTextContent('Odłożone środki');
    expect(card).toHaveTextContent('Plan bieżącego miesiąca');
    expect(within(card).getByRole('progressbar',{name:'Wykonanie odłożeń: Prąd'})).toHaveAttribute('aria-valuenow','100');
    expect(within(card).queryByRole('progressbar',{name:'Postęp: Prąd'})).not.toBeInTheDocument();
    fireEvent.click(within(card).getByRole('button',{name:'Zapisz płatność'}));
    expect(screen.getByRole('dialog')).toHaveTextContent('Miesięczna pula pozostanie aktywna');
    expect(screen.getByRole('dialog')).not.toHaveTextContent('Rozpocznie się kolejny roczny cykl');
  });
  it('can convert an existing reserve without recording its saved funds again',async()=>{
    show();await screen.findByRole('heading',{name:reserve.name});
    fireEvent.click(screen.getByRole('button',{name:`Edytuj rezerwę: ${reserve.name}`}));
    expect(screen.getByLabelText('Sposób planowania')).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Sposób planowania'),{target:{value:'MONTHLY'}});
    fireEvent.change(screen.getByLabelText('Domyślna kwota miesięczna w PLN'),{target:{value:'250'}});
    fireEvent.change(screen.getByLabelText('Kategoria przyszłej płatności'),{target:{value:'2'}});
    expect(screen.getByRole('dialog')).toHaveTextContent('Zachowamy odłożone środki');
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Zapisz zmiany'}));
    await waitFor(()=>expect(reservesApi.update).toHaveBeenCalledWith(7,expect.objectContaining({monthly_amount:250,category_id:2}),2));
    expect(reservesApi.move).not.toHaveBeenCalled();
  });
  it('settles an already imported payment without submitting a new expense',async()=>{
    vi.mocked(budgetImportsApi.matches).mockResolvedValue([{id:9,account_id:1,account_name:'Konto',date:'2026-10-02',amount:2400,
      description:'Roczna polisa',merchant:'Ubezpieczyciel',version:3,has_receipt:true,classification_status:'GENERAL',merchant_match:false,
      lines:[{category_id:2,category_name:'Ubezpieczenia',amount:2400,label:''}]}]);
    show();await screen.findByRole('heading',{name:reserve.name});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz płatność'}));
    fireEvent.change(screen.getByLabelText('Płatność w budżecie'),{target:{value:'EXISTING'}});
    fireEvent.click(screen.getByRole('button',{name:'Znajdź zapisany wydatek'}));
    await screen.findByLabelText('Zapisany wydatek');
    fireEvent.change(screen.getByLabelText('Zapisany wydatek'),{target:{value:'9'}});
    expect(screen.getByLabelText('Data operacji')).toHaveValue('2026-10-02');
    expect(screen.queryByLabelText('Kategoria wydatku')).not.toBeInTheDocument();
    await review();fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Zapisz płatność'}));
    await screen.findByText('Rezerwa rozliczona z istniejącą płatnością. Wydatek i saldo nie zostały zapisane ponownie.');
    expect(reservesApi.move).toHaveBeenCalledWith(7,{kind:'SPEND',account_id:1,amount:2400,date:'2026-10-02',notes:'',
      existing_entry_id:9,entry_version:3,expected_state:'snapshot'},2,expect.any(String));
  });
  it('shows the server-calculated saving plan, earmarked cash and contribution history',async()=>{
    show();await screen.findByRole('heading',{name:reserve.name});
    expect(screen.getByText(/Nowe odłożenie obciąża budżet miesiąca/)).toBeInTheDocument();
    const card=screen.getByRole('heading',{name:reserve.name}).closest('article')!;
    expect(card).toHaveTextContent('172,73');expect(card).toHaveTextContent('Miesiące do odkładania: 11');
    expect(screen.getByText('Pierwsza kwota',{exact:false})).toBeInTheDocument();
    expect(screen.getByRole('progressbar',{name:'Postęp: Ubezpieczenie auta'})).toHaveAttribute('aria-valuenow','20.83');
    expect(reservesApi.move).not.toHaveBeenCalled();
  });

  it('requires a budget account and provides a clear route to create one',async()=>{
    get.mockResolvedValue({...workspace(),accounts:[],items:[],totals:{saved:0,remaining:0,monthly_required:0,urgent_amount:0,active:0}});
    show();await screen.findByText('Zacznij od konta budżetowego');
    expect(screen.getByRole('button',{name:'Nowa rezerwa'})).toBeDisabled();
    expect(screen.getByRole('link',{name:'Dodaj konto w budżecie'})).toHaveAttribute('href','/budget');
  });

  it('preserves the create draft and retry identity after an unconfirmed save',async()=>{
    vi.mocked(reservesApi.create).mockRejectedValueOnce(new Error('Nie potwierdzono zapisu'));
    show();await screen.findByRole('heading',{name:reserve.name});fireEvent.click(screen.getByRole('button',{name:'Nowa rezerwa'}));
    fireEvent.change(screen.getByLabelText('Nazwa rezerwy'),{target:{value:'Ubezpieczenie mieszkania'}});
    fireEvent.change(screen.getByLabelText('Przewidywany koszt w PLN'),{target:{value:'600'}});
    fireEvent.change(screen.getByLabelText('Termin wydatku'),{target:{value:'2027-06-01'}});
    fireEvent.submit(screen.getByLabelText('Nazwa rezerwy').closest('form')!);
    await screen.findByText('Nie potwierdzono zapisu');
    expect(screen.getByLabelText('Nazwa rezerwy')).toHaveValue('Ubezpieczenie mieszkania');
    fireEvent.submit(screen.getByLabelText('Nazwa rezerwy').closest('form')!);
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const calls=vi.mocked(reservesApi.create).mock.calls;
    expect(calls[0][1]).toBe(calls[1][1]);
    expect(calls[1][0]).toMatchObject({target_amount:600,account_id:1,frequency:'YEARLY',due_date:'2027-06-01'});
  });

  it('accepts an irregular contribution and displays the recalculated result after reload',async()=>{
    const next=workspace();next.items[0]={...reserve,saved:1000,remaining:1400,monthly_required:127.28,version:3};
    get.mockResolvedValueOnce(workspace()).mockResolvedValue(next);
    show();await screen.findByRole('heading',{name:reserve.name});fireEvent.click(screen.getByRole('button',{name:'Odłóż środki'}));
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'500'}});
    await review();fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);
    await screen.findByText('Środki odłożone. Plan kolejnych miesięcy został przeliczony.');
    expect(reservesApi.move).toHaveBeenCalledWith(7,expect.objectContaining({kind:'ADD',amount:500}),2,expect.any(String));
    await waitFor(()=>expect(screen.getByRole('heading',{name:reserve.name}).closest('article')).toHaveTextContent('127,28'));
  });

  it('does not submit a successful contribution twice when refreshing fails',async()=>{
    get.mockResolvedValueOnce(workspace()).mockRejectedValue(new Error('Błąd odczytu'));
    show();await screen.findByRole('heading',{name:reserve.name});fireEvent.click(screen.getByRole('button',{name:'Odłóż środki'}));
    await review();fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);
    await screen.findByRole('alert');expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Spróbuj ponownie'}));
    await waitFor(()=>expect(get).toHaveBeenCalledTimes(3));expect(reservesApi.move).toHaveBeenCalledTimes(1);
  });

  it('records an actual payment with its category and explains renewal of the yearly cycle',async()=>{
    show();await screen.findByRole('heading',{name:reserve.name});fireEvent.click(screen.getByRole('button',{name:'Zapisz płatność'}));
    const dialog=screen.getByRole('dialog');
    expect(dialog).toHaveTextContent('Rozpocznie się kolejny roczny cykl.');
    fireEvent.change(screen.getByLabelText('Zapłacona kwota w PLN'),{target:{value:'2300'}});
    await review();fireEvent.click(within(dialog).getByRole('button',{name:'Zapisz płatność'}));
    await screen.findByText('Płatność zapisana w budżecie i rezerwa rozliczona.');
    expect(reservesApi.move).toHaveBeenCalledWith(7,expect.objectContaining({kind:'SPEND',amount:2300,category_id:2}),2,expect.any(String));
  });

  it('preserves a contribution after a version conflict and allows releasing money separately',async()=>{
    vi.mocked(reservesApi.move).mockRejectedValueOnce(new Error('Rezerwa została zmieniona'));
    show();await screen.findByRole('heading',{name:reserve.name});fireEvent.click(screen.getByRole('button',{name:'Zwolnij'}));
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'100'}});
    await review();fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);
    await screen.findByText('Rezerwa została zmieniona');expect(screen.getByLabelText('Kwota w PLN')).toHaveValue(100);
    expect(reservesApi.move).toHaveBeenCalledWith(7,expect.objectContaining({kind:'RELEASE',amount:100}),2,expect.any(String));
  });

  it('shows unavailable data instead of an empty successful summary',async()=>{
    get.mockRejectedValue(new Error('Serwer niedostępny'));show();await screen.findByRole('alert');
    expect(screen.queryByRole('region',{name:'Podsumowanie rezerw'})).not.toBeInTheDocument();
  });
});

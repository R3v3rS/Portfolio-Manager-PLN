import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import BudgetAccounts from './BudgetAccounts';
import { accountsApi, type AccountsWorkspace } from '../api_accounts';

vi.mock('../api_accounts',()=>({accountsApi:{get:vi.fn(),create:vi.fn(),transfer:vi.fn(),reconcile:vi.fn(),openingBalance:vi.fn()}}));
const workspace=():AccountsWorkspace=>({as_of:'2026-10-02',totals:{balance:10000,reserved:800,available:9200},warnings:[],
  accounts:[{id:1,name:'Konto osobiste',balance:8000,reserved:500,available:7500,verified_on:'2026-10-02',allocations:[{reserve_id:7,name:'Ubezpieczenie auta',amount:500,due_date:'2027-09-30',version:2}]},
    {id:2,name:'Konto oszczędnościowe',balance:2000,reserved:300,available:1700,verified_on:null,allocations:[{reserve_id:7,name:'Ubezpieczenie auta',amount:300,due_date:'2027-09-30',version:2}]}],
  reserves:[{id:7,name:'Ubezpieczenie auta',version:2,locations:[{account_id:1,account_name:'Konto osobiste',amount:500},{account_id:2,account_name:'Konto oszczędnościowe',amount:300}]}],history:[]});
const show=(path='/budget/accounts')=>render(<MemoryRouter initialEntries={[path]}><BudgetAccounts/></MemoryRouter>);
beforeEach(()=>{vi.resetAllMocks();vi.mocked(accountsApi.get).mockResolvedValue(workspace());vi.mocked(accountsApi.create).mockResolvedValue({id:3});vi.mocked(accountsApi.transfer).mockResolvedValue({id:1});vi.mocked(accountsApi.reconcile).mockResolvedValue({id:1});});

describe('Budget accounts',()=>{
  it('creates a credit card using the outstanding debt, without using the credit limit as cash',async()=>{
    show();await screen.findByRole('heading',{name:'Konto osobiste'});
    fireEvent.click(screen.getByRole('button',{name:'Dodaj konto'}));
    fireEvent.change(screen.getByLabelText('Rodzaj konta'),{target:{value:'CREDIT_CARD'}});
    fireEvent.change(screen.getByLabelText('Nazwa konta'),{target:{value:'Kredytówka'}});
    fireEvent.change(screen.getByLabelText('Obecne zadłużenie w PLN'),{target:{value:'300'}});
    expect(screen.getByText(/Nie wpisuj limitu kredytowego/)).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Dodaj konto'}));
    await waitFor(()=>expect(accountsApi.create).toHaveBeenCalledWith('Kredytówka',-300,expect.any(String),'CREDIT_CARD'));
  });

  it('repays a card with a transfer and previews cash and debt instead of recording an expense',async()=>{
    const data=workspace();data.accounts.push({id:3,name:'Kredytówka',account_type:'CREDIT_CARD',balance:-300,reserved:0,available:-300,verified_on:null,allocations:[]});
    data.totals={...data.totals,balance:9700,available:8900,cash_balance:10000,credit_card_debt:300};
    vi.mocked(accountsApi.get).mockResolvedValue(data);
    show();const card=(await screen.findByRole('heading',{name:'Kredytówka'})).closest('article')!;
    expect(card).toHaveTextContent('Zadłużenie do spłaty300,00');
    expect(within(card).queryByText('Odłożone na tym koncie')).not.toBeInTheDocument();
    fireEvent.click(within(card).getByRole('button',{name:'Zapisz spłatę'}));
    const dialog=within(screen.getByRole('dialog',{name:'Zapisz spłatę karty'}));
    expect(dialog.getByLabelText('Kwota w PLN')).toHaveValue(300);
    expect(dialog.getByLabelText('Na konto')).toHaveValue('3');
    expect(dialog.queryByLabelText('Cel przelewu')).not.toBeInTheDocument();
    expect(dialog.getByRole('status')).toHaveTextContent(/300,00.*0,00/);
    expect(within(dialog.getByLabelText('Z konta')).queryByRole('option',{name:'Kredytówka'})).not.toBeInTheDocument();
    fireEvent.click(dialog.getByRole('button',{name:'Zapisz spłatę'}));
    await waitFor(()=>expect(accountsApi.transfer).toHaveBeenCalledWith(expect.objectContaining({source_account_id:1,target_account_id:3,amount:300,reserve_id:null,move_money:true,reserve_action:'MOVE'}),expect.any(String)));
    await screen.findByText(/Spłata karty zapisana.*nie jest drugim kosztem/);
  });

  it('blocks repayment when the selected bank account has insufficient unreserved cash',async()=>{
    const data=workspace();data.accounts.push({id:3,name:'Kredytówka',account_type:'CREDIT_CARD',balance:-7800,reserved:0,available:-7800,verified_on:null,allocations:[]});
    vi.mocked(accountsApi.get).mockResolvedValue(data);
    show();await screen.findByRole('heading',{name:'Kredytówka'});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz spłatę'}));
    expect(screen.getByText(/Brakuje środków poza rezerwami na koncie spłaty/)).toBeInTheDocument();
    expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Zapisz spłatę'})).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'7500'}});
    expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Zapisz spłatę'})).toBeEnabled();
    expect(accountsApi.transfer).not.toHaveBeenCalled();
  });

  it('allows signed balance reconciliation for a card without a reserve shortage warning',async()=>{
    const data=workspace();data.accounts[1]={...data.accounts[1],name:'Kredytówka',account_type:'CREDIT_CARD',balance:-300,available:-300,reserved:0,allocations:[]};
    vi.mocked(accountsApi.get).mockResolvedValue(data);
    show();const card=(await screen.findByRole('heading',{name:'Kredytówka'})).closest('article')!;
    fireEvent.click(within(card).getByRole('button',{name:'Sprawdź saldo'}));
    fireEvent.change(screen.getByLabelText('Saldo karty w PLN (minus oznacza dług)'),{target:{value:'-350'}});
    fireEvent.change(screen.getByLabelText('Powód różnicy / notatka'),{target:{value:'Brakujący zapis'}});
    expect(screen.queryByText(/Saldo będzie niższe niż zapisane rezerwy/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Potwierdź saldo'}));
    await waitFor(()=>expect(accountsApi.reconcile).toHaveBeenCalledWith(2,-350,-300,'Brakujący zapis',expect.any(String)));
  });

  it('marks an existing correction as opening data while preserving the current balance',async()=>{
    const data=workspace();data.accounts[1]={...data.accounts[1],name:'Alior Bank',balance:847,opening_balance:null,opening_record_id:null,inferred_opening_balance:0};
    data.history=[{id:'r1',kind:'RECONCILIATION',date:'2026-10-03',created_at:'2026-10-03',account_id:2,
      source_account_id:null,target_account_id:null,title:'Alior Bank',detail:'',notes:'Początkowa kwota',amount:912,previous_balance:-65,observed_balance:847}];
    vi.mocked(accountsApi.get).mockResolvedValue(data);
    vi.mocked(accountsApi.openingBalance).mockResolvedValue({id:2});
    show();await screen.findByRole('heading',{name:'Alior Bank'});
    fireEvent.click(screen.getByRole('button',{name:'To saldo początkowe'}));
    const dialog=within(screen.getByRole('dialog',{name:'Oznacz jako saldo początkowe'}));
    expect(dialog.getByLabelText('Saldo początkowe w PLN')).toHaveValue(912);
    expect(dialog.getByLabelText('Saldo początkowe w PLN')).toHaveAttribute('readonly');
    expect(dialog.getByText(/Saldo konta po zapisie: 847,00/)).toBeInTheDocument();
    fireEvent.click(dialog.getByRole('button',{name:'Oznacz jako saldo początkowe'}));
    await waitFor(()=>expect(accountsApi.openingBalance).toHaveBeenCalledWith(2,{from_reconciliation_id:1,
      expected_balance:847,expected_opening_id:null,notes:''},expect.any(String)));
    expect(accountsApi.reconcile).not.toHaveBeenCalled();expect(accountsApi.transfer).not.toHaveBeenCalled();
  });

  it('shows opening balance at the account and edits it separately from income',async()=>{
    const data=workspace();data.accounts[1]={...data.accounts[1],name:'Alior Bank',balance:847,opening_balance:912,opening_record_id:2,inferred_opening_balance:912,opening_date:'2026-10-01'};
    vi.mocked(accountsApi.get).mockResolvedValue(data);vi.mocked(accountsApi.openingBalance).mockResolvedValue({id:3});
    show();const card=(await screen.findByRole('heading',{name:'Alior Bank'})).closest('article')!;
    expect(card).toHaveTextContent(/Saldo początkowe912,00/);
    fireEvent.click(within(card).getByRole('button',{name:'Edytuj saldo początkowe'}));
    fireEvent.change(screen.getByLabelText('Saldo początkowe w PLN'),{target:{value:'1000'}});
    expect(screen.getByText(/Saldo konta po zapisie: 935,00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Zapisz saldo początkowe'}));
    await waitFor(()=>expect(accountsApi.openingBalance).toHaveBeenCalledWith(2,{balance:1000,expected_balance:847,expected_opening_id:2,notes:''},expect.any(String)));
    expect(accountsApi.reconcile).not.toHaveBeenCalled();
  });
  it('funds a reserve using free source cash and clearly charges the month',async()=>{
    const data=workspace();data.reserves[0].locations=[];
    vi.mocked(accountsApi.get).mockResolvedValue(data);
    show();await screen.findByRole('heading',{name:'Konto osobiste'});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz przelew'}));
    fireEvent.change(screen.getByLabelText('Cel przelewu'),{target:{value:'FUND'}});
    fireEvent.change(screen.getByLabelText('Rezerwa do zasilenia'),{target:{value:'7'}});
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'150'}});
    expect(screen.queryByLabelText('Sposób przeniesienia')).not.toBeInTheDocument();
    expect(screen.getByText(/Średnia kolejnych wpłat przeliczy się automatycznie/)).toBeInTheDocument();
    fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);
    await screen.findByText(/Odłożono 150,00.*Ubezpieczenie auta/);
    expect(accountsApi.transfer).toHaveBeenCalledWith(expect.objectContaining({source_account_id:1,target_account_id:2,
      reserve_id:7,reserve_action:'FUND',amount:150,move_money:true,version:2}),expect.any(String));
  });
  it('shows where each part of the reserve is held without counting it twice',async()=>{
    show();await screen.findByRole('heading',{name:'Konto osobiste'});
    const card=screen.getByRole('heading',{name:'Konto osobiste'}).closest('article')!;
    expect(card).toHaveTextContent(/8\s?000,00/);
    expect(card).toHaveTextContent('500,00');expect(card).toHaveTextContent(/7\s?500,00/);
    expect(within(card).getByRole('link',{name:'Ubezpieczenie auta'})).toHaveAttribute('href','/budget/reserves?reserve=7');
    expect(accountsApi.transfer).not.toHaveBeenCalled();
  });

  it('records a real transfer of earmarked funds with both balances and reserve version',async()=>{
    show();await screen.findByRole('heading',{name:'Konto osobiste'});fireEvent.click(screen.getByRole('button',{name:'Zapisz przelew'}));
    fireEvent.change(screen.getByLabelText('Jakie środki przenosisz'),{target:{value:'7'}});
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'200'}});
    fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);
    await screen.findByText('Przelew zapisany. Salda i miejsca odłożenia środków zostały zaktualizowane.');
    expect(accountsApi.transfer).toHaveBeenCalledWith(expect.objectContaining({source_account_id:1,target_account_id:2,amount:200,
      reserve_id:7,version:2,move_money:true,source_balance:8000,target_balance:2000}),expect.any(String));
  });

  it('opens a specific reserve and permits moving only its location',async()=>{
    show('/budget/accounts?reserve=7');await screen.findByRole('dialog');
    expect(screen.getByLabelText('Jakie środki przenosisz')).toHaveValue('7');
    fireEvent.change(screen.getByLabelText('Sposób przeniesienia'),{target:{value:'LOCATION'}});
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'100'}});
    fireEvent.click(screen.getByRole('button',{name:'Przenieś przypisanie'}));
    await screen.findByText('Miejsce rezerwy zmienione. Salda kont pozostały bez zmian.');
    expect(accountsApi.transfer).toHaveBeenCalledWith(expect.objectContaining({reserve_id:7,move_money:false}),expect.any(String));
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('retains draft and request identity after an uncertain response',async()=>{
    vi.mocked(accountsApi.transfer).mockRejectedValueOnce(new Error('Brak potwierdzenia'));
    show();await screen.findByRole('heading',{name:'Konto osobiste'});fireEvent.click(screen.getByRole('button',{name:'Zapisz przelew'}));
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'250'}});
    fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);await screen.findByText('Brak potwierdzenia');
    expect(screen.getByLabelText('Kwota w PLN')).toHaveValue(250);
    fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);await waitFor(()=>expect(accountsApi.transfer).toHaveBeenCalledTimes(2));
    expect(vi.mocked(accountsApi.transfer).mock.calls[0][1]).toBe(vi.mocked(accountsApi.transfer).mock.calls[1][1]);
  });

  it('reconciles the bank balance separately and shows an insufficient reserve warning',async()=>{
    show();await screen.findByRole('heading',{name:'Konto osobiste'});
    const card=screen.getByRole('heading',{name:'Konto osobiste'}).closest('article')!;
    fireEvent.click(within(card).getByRole('button',{name:'Sprawdź saldo'}));
    fireEvent.change(screen.getByLabelText('Aktualne saldo w banku w PLN'),{target:{value:'400'}});
    await screen.findByText(/Saldo będzie niższe niż zapisane rezerwy/);
    fireEvent.change(screen.getByLabelText('Powód różnicy / notatka'),{target:{value:'Brakujące wydatki'}});
    fireEvent.click(screen.getByRole('button',{name:'Potwierdź saldo'}));
    await waitFor(()=>expect(accountsApi.reconcile).toHaveBeenCalledWith(1,400,8000,'Brakujące wydatki',expect.any(String)));
  });

  it('offers account creation when there are no balances and prevents transfers',async()=>{
    vi.mocked(accountsApi.get).mockResolvedValue({...workspace(),accounts:[],reserves:[],totals:{balance:0,reserved:0,available:0}});
    show();await screen.findByRole('heading',{name:'Dodaj konta, z których korzystasz'});
    expect(screen.getByRole('button',{name:'Zapisz przelew'})).toBeDisabled();
    fireEvent.click(screen.getByRole('button',{name:'Dodaj pierwsze konto'}));
    fireEvent.change(screen.getByLabelText('Nazwa konta'),{target:{value:'Gotówka'}});
    fireEvent.change(screen.getByLabelText('Saldo początkowe w PLN'),{target:{value:'200'}});
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Dodaj konto'}));
    await waitFor(()=>expect(accountsApi.create).toHaveBeenCalledWith('Gotówka',200,expect.any(String)));
  });

  it('closes a confirmed save even if reloading fails and does not write it twice',async()=>{
    vi.mocked(accountsApi.get).mockResolvedValueOnce(workspace()).mockRejectedValue(new Error('Błąd odczytu'));
    show();await screen.findByRole('heading',{name:'Konto osobiste'});fireEvent.click(screen.getByRole('button',{name:'Zapisz przelew'}));
    fireEvent.change(screen.getByLabelText('Kwota w PLN'),{target:{value:'100'}});fireEvent.submit(screen.getByLabelText('Kwota w PLN').closest('form')!);
    await screen.findByRole('alert');expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Odśwież dane'}));await waitFor(()=>expect(accountsApi.get).toHaveBeenCalledTimes(3));
    expect(accountsApi.transfer).toHaveBeenCalledTimes(1);
  });
});

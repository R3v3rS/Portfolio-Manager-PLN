import {fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {beforeEach,describe,expect,it,vi} from 'vitest';
import {planningApi} from '../../api_planning';
import {budgetWorkspaceApi,type BudgetWorkspace} from '../../api_budget_workspace';
import {BudgetReservePlans,BudgetCarryoverPolicies} from './BudgetReservePlans';
import BudgetPurchases from './BudgetPurchases';
import BudgetObligations from './BudgetObligations';
import {BudgetPayCycle,BudgetPlanningOverview} from './BudgetPlanningOverview';

vi.mock('../../api_planning',()=>({planningApi:{reservePlan:vi.fn(),policy:vi.fn(),closeMonth:vi.fn(),createPurchase:vi.fn(),updatePurchase:vi.fn(),settings:vi.fn()}}));
vi.mock('../../api_budget_workspace',()=>({budgetWorkspaceApi:{createBill:vi.fn(),updateBill:vi.fn(),payBill:vi.fn()}}));
vi.mock('../charts/ChartKit',()=>({TrendChart:()=>null}));
const fixture=():BudgetWorkspace=>({month:'2026-10',accounts:[{id:1,name:'PKO',balance:3000,currency:'PLN'},{id:2,name:'Alior',balance:500,currency:'PLN'}],
  categories:[{id:3,name:'Transport',icon:'',manual_plan:400,planned_bills:0,planned:400,spent:200,remaining:200}],entries:[],bills:[],
  totals:{balance:3500,income:0,spent:200,planned:400,remaining_in_plan:200,to_plan:2800},
  planning:{settings:{id:1,pay_day:10,income_id:null,spending_account_id:1,loan_account_id:1,version:2,resolved_pay_day:10,resolved_income_id:null,resolved_spending_account_id:1,resolved_loan_account_id:1},
    reserve_plans:[{reserve_id:4,name:'OC auta',account_id:2,account_name:'Alior',due_date:'2027-10-03',recommended:200,planned:500,funded:100,remaining:400,priority:1,version:3,reserve_version:2,active:true}],
    policies:[{category_id:3,name:'Transport',mode:'RESET',reserve_id:null,start_month:'2026-10',version:0}],purchases:[],bill_catalog:[],closing:{},
    cycle:{start:'2026-10-10',end:'2026-11-09',income:0,spent:200,expected_income:6000,bills_before_payday:100,next_payday:'2026-10-10'}}});
const reload=vi.fn(async()=>undefined);
const show=(node:React.ReactNode)=>render(<MemoryRouter>{node}</MemoryRouter>);
beforeEach(()=>{vi.resetAllMocks();for(const fn of Object.values(planningApi))vi.mocked(fn).mockResolvedValue({});vi.mocked(budgetWorkspaceApi.createBill).mockResolvedValue({id:8});vi.mocked(budgetWorkspaceApi.updateBill).mockResolvedValue({id:8});vi.mocked(budgetWorkspaceApi.payBill).mockResolvedValue({entry_id:9});});

describe('Household planning controls',()=>{
  it('keeps paid bill actions folded while pending payments remain visible',()=>{
    const data=fixture();
    data.bills=[{id:1,title:'Czynsz',amount:800,due_date:'2026-10-10',frequency:'MONTHLY',account_id:1,account_name:'PKO',category_id:3,category_name:'Transport',status:'PAID',entry_id:9},{id:2,title:'Telefon',amount:55,due_date:'2026-10-15',frequency:'MONTHLY',account_id:1,account_name:'PKO',category_id:3,category_name:'Transport',status:'UPCOMING',entry_id:null}];
    show(<BudgetObligations data={data} reload={reload}/>);
    expect(screen.getByRole('heading',{name:'Telefon'})).toBeInTheDocument();
    const paidSection=screen.getByText(/Opłacone rachunki \(1\)/).closest('details');
    expect(paidSection).not.toHaveAttribute('open');
    fireEvent.click(screen.getByText(/Opłacone rachunki \(1\)/));
    expect(paidSection).toHaveAttribute('open');
    expect(screen.getByRole('heading',{name:'Czynsz'})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Cofnij rozliczenie'})).toBeInTheDocument();
    expect(budgetWorkspaceApi.payBill).not.toHaveBeenCalled();
  });
  it('creates a one-off bill with an exact payment date by default',async()=>{
    show(<BudgetObligations data={fixture()} reload={reload}/>);
    fireEvent.click(screen.getByRole('button',{name:'Dodaj zobowiązanie'}));
    const dialog=within(screen.getByRole('dialog'));
    expect(dialog.getByRole('radio',{name:/Jednorazowy/})).toBeChecked();
    expect(dialog.queryByLabelText('Powtarzalność')).not.toBeInTheDocument();
    fireEvent.change(dialog.getByLabelText('Nazwa'),{target:{value:'Prezent'}});
    fireEvent.change(dialog.getByLabelText('Kwota w PLN'),{target:{value:'27'}});
    fireEvent.change(dialog.getByLabelText('Termin płatności'),{target:{value:'2026-10-22'}});
    fireEvent.click(dialog.getByRole('button',{name:'Zapisz zobowiązanie'}));
    await waitFor(()=>expect(budgetWorkspaceApi.createBill).toHaveBeenCalledWith(expect.objectContaining({frequency:'ONCE',due_month:'2026-10',due_day:22,amount:27})));
  });
  it('requires choosing recurrence and filters one-off bills separately',()=>{
    const data=fixture();data.bills=[{id:1,title:'Prezent',amount:27,due_date:'2026-10-22',frequency:'ONCE',account_id:1,account_name:'PKO',category_id:3,category_name:'Transport',status:'UPCOMING',entry_id:null},{id:2,title:'Telefon',amount:55,due_date:'2026-10-10',frequency:'MONTHLY',account_id:1,account_name:'PKO',category_id:3,category_name:'Transport',status:'UPCOMING',entry_id:null}];
    show(<BudgetObligations data={data} reload={reload}/>);
    expect(screen.getByRole('heading',{name:'Rachunki jednorazowe'})).toBeInTheDocument();
    expect(screen.getByRole('heading',{name:'Rachunki powtarzalne'})).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Rodzaj rachunków'),{target:{value:'ONCE'}});
    expect(screen.queryByRole('heading',{name:'Telefon'})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Dodaj zobowiązanie'}));
    const dialog=within(screen.getByRole('dialog'));
    fireEvent.click(dialog.getByRole('radio',{name:/Powtarzalny/}));
    expect(dialog.getByLabelText('Powtarzalność')).toHaveValue('MONTHLY');
    expect(dialog.getByLabelText('Pierwszy miesiąc')).toBeInTheDocument();
    expect(dialog.queryByLabelText('Termin płatności')).not.toBeInTheDocument();
  });
  it('shows monthly income funds independently of the account cash card',()=>{
    const data=fixture();data.totals={...data.totals,income:1000,expected_income:200,monthly_income_total:1200,monthly_income_cost:300,monthly_income_remaining_plan:800,monthly_income_to_plan:100};
    show(<BudgetPlanningOverview data={data} forecast={null} failed={false}/>);
    const monthly=within(screen.getByRole('article',{name:'Wolne z przychodów miesiąca'}));
    expect(monthly.getByText('100,00 zł',{exact:false})).toBeInTheDocument();
    expect(screen.getByText(/otrzymano.*1\s?000,00.*oczekiwane.*200,00/)).toBeInTheDocument();
    expect(monthly.getByText(/Bez wcześniejszych sald/)).toBeInTheDocument();
    expect(screen.getByText(/3\s?500,00/,{selector:'strong'})).toBeInTheDocument();
  });
  it('keeps an open reserve plan fixed and available for manual funding at zero',()=>{
    const data=fixture();data.planning!.reserve_plans[0]={...data.planning!.reserve_plans[0],name:'Poduszka',open_ended:true,monthly_amount:0,planned:0,funded:333,remaining:0};
    show(<BudgetReservePlans data={data} reload={reload}/>);
    expect(screen.getByLabelText('Plan odłożenia: Poduszka')).toHaveAttribute('readonly');
    expect(screen.queryByRole('button',{name:'Zapisz plan'})).not.toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Zmień stałą kwotę'})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Odłóż'})).toBeEnabled();
    expect(planningApi.reservePlan).not.toHaveBeenCalled();
  });
  it('corrects only the selected month of a media pool and exposes invoice settlement',async()=>{
    const data=fixture();data.planning!.reserve_plans[0]={...data.planning!.reserve_plans[0],name:'Prąd',monthly_amount:250,planned:250,funded:180,remaining:70};
    show(<BudgetReservePlans data={data} reload={reload}/>);
    expect(screen.getByText(/Domyślnie.*250,00/)).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Rozlicz fakturę'})).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Plan odłożenia: Prąd'),{target:{value:'220'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz plan'}));
    await waitFor(()=>expect(planningApi.reservePlan).toHaveBeenCalledWith(4,{month:'2026-10',amount:220,priority:1,version:3}));
    expect(budgetWorkspaceApi.payBill).not.toHaveBeenCalled();
  });
  it('links a bank payment to the bill without asking to debit the account again',async()=>{
    const data=fixture();data.bills=[{id:8,title:'ENEA',account_id:1,account_name:'PKO',category_id:3,category_name:'Transport',frequency:'MONTHLY',amount:250,due_date:'2026-10-15',status:'UPCOMING',entry_id:null,version:2,payment_candidates:[{id:9,description:'ENEA SA',amount:250,date:'2026-10-02',version:3}]}];
    show(<BudgetObligations data={data} reload={reload}/>);
    fireEvent.click(screen.getByRole('button',{name:'Znaleziono płatność — powiąż'}));
    const dialog=within(screen.getByRole('dialog'));
    expect(dialog.getByLabelText('Powiązanie z istniejącą transakcją')).toHaveValue('9');
    expect(dialog.getByText(/3\s?000,00.*3\s?000,00/)).toBeInTheDocument();
    fireEvent.click(dialog.getByRole('button',{name:'Powiąż płatność'}));
    await waitFor(()=>expect(budgetWorkspaceApi.payBill).toHaveBeenCalledWith(8,'2026-10','2026-10-02',expect.objectContaining({existing_entry_id:9,entry_version:3,amount:250,version:2})));
  });
  it('requires an explicit separate-payment confirmation when a matching purchase exists',()=>{
    const data=fixture();data.bills=[{id:8,title:'ENEA',account_id:1,account_name:'PKO',category_id:3,category_name:'Transport',frequency:'MONTHLY',amount:250,due_date:'2026-10-15',status:'UPCOMING',entry_id:null,version:2,payment_candidates:[{id:9,description:'ENEA SA',amount:250,date:'2026-10-02',version:3}]}];
    show(<BudgetObligations data={data} reload={reload}/>);fireEvent.click(screen.getByRole('button',{name:'Znaleziono płatność — powiąż'}));
    const dialog=within(screen.getByRole('dialog'));fireEvent.change(dialog.getByLabelText('Powiązanie z istniejącą transakcją'),{target:{value:''}});
    expect(dialog.getByRole('button',{name:'Zapisz opłacenie'})).toBeDisabled();
    fireEvent.click(dialog.getByRole('checkbox',{name:/To osobna płatność/}));expect(dialog.getByRole('button',{name:'Zapisz opłacenie'})).toBeEnabled();
    expect(budgetWorkspaceApi.payBill).not.toHaveBeenCalled();
  });
  it('warns before linking a payment assigned to a different category',()=>{
    const data=fixture();data.bills=[{id:8,title:'ENEA',account_id:1,account_name:'PKO',category_id:3,category_name:'Transport',frequency:'MONTHLY',amount:250,due_date:'2026-10-15',status:'UPCOMING',entry_id:null,version:2,payment_candidates:[{id:9,description:'ENEA SA',amount:250,date:'2026-10-02',version:3}]}];
    data.entries=[{id:9,account_id:1,account_name:'PKO',kind:'EXPENSE',description:'ENEA SA',merchant:'ENEA',amount:250,date:'2026-10-02',has_receipt:false,bill_id:null,loan_id:null,classification_status:'GENERAL',lines:[{category_id:7,category_name:'Jedzenie',amount:250,label:''}]}];
    show(<BudgetObligations data={data} reload={reload}/>);
    fireEvent.click(screen.getByRole('button',{name:'Znaleziono płatność — powiąż'}));
    expect(screen.getByRole('alert')).toHaveTextContent('Ten wydatek ma inną kategorię');
    expect(screen.getByRole('button',{name:'Powiąż płatność'})).toBeDisabled();
    expect(screen.getByRole('link',{name:'Popraw kategorię wydatku'})).toHaveAttribute('href','/budget?view=entries&month=2026-10');
    expect(budgetWorkspaceApi.payBill).not.toHaveBeenCalled();
  });
  it('saves a monthly reserve target with priority and version, without recording a contribution',async()=>{
    show(<BudgetReservePlans data={fixture()} reload={reload}/>);
    fireEvent.change(screen.getByLabelText('Plan odłożenia: OC auta'),{target:{value:'650'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz plan'}));
    await waitFor(()=>expect(planningApi.reservePlan).toHaveBeenCalledWith(4,{month:'2026-10',amount:650,priority:1,version:3}));
    expect(screen.getByText(/Plan pomniejsza/)).toBeInTheDocument();
    expect(budgetWorkspaceApi.payBill).not.toHaveBeenCalled();
  });
  it('keeps an explicitly saved zero target instead of replacing it with the recommendation',()=>{
    const data=fixture();data.planning!.reserve_plans[0].planned=0;
    show(<BudgetReservePlans data={data} reload={reload}/>);
    expect(screen.getByLabelText('Plan odłożenia: OC auta')).toHaveValue(0);
  });
  it('requires the closing preview before moving a remaining limit to its reserve',async()=>{
    const data=fixture();data.month='2026-09';data.planning!.policies[0]={...data.planning!.policies[0],mode:'RESERVE',reserve_id:4,start_month:'2026-09',version:2};
    show(<BudgetCarryoverPolicies data={data} reload={reload}/>);
    expect(planningApi.closeMonth).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Zamknij miesiąc i rozlicz limity'}));
    const dialog=within(screen.getByRole('dialog'));
    expect(dialog.getByText(/Transport → OC auta/)).toBeInTheDocument();
    expect(planningApi.closeMonth).not.toHaveBeenCalled();
    fireEvent.click(dialog.getByRole('button',{name:'Potwierdź zamknięcie'}));
    await waitFor(()=>expect(planningApi.closeMonth).toHaveBeenCalledWith('2026-09',{'3':2},expect.any(String),{'3':200},undefined));
  });
  it('opens a purchase variant only as a forecast scenario',()=>{
    const data=fixture();data.planning!.purchases=[{id:5,name:'Wakacje',amount:1200,low:900,high:1800,due_date:'2027-01-15',account_id:2,account_name:'Alior',category_id:3,status:'PLANNED',notes:'',reserve_id:4,saved:100,monthly_required:300,version:1,reserve_version:2}];
    show(<BudgetPurchases data={data} reload={reload}/>);
    fireEvent.change(screen.getByLabelText('Wariant'),{target:{value:'LOW'}});
    const link=screen.getByRole('link',{name:'Sprawdź wpływ na przyszłe saldo'});
    expect(link).toHaveAttribute('href',expect.stringContaining('purchase_amount=900'));
    expect(link).toHaveAttribute('href',expect.stringContaining('purchase=5'));
    expect(planningApi.updatePurchase).not.toHaveBeenCalled();
  });
  it('edits a purchase with the reserve version to protect concurrent funding changes',async()=>{
    const data=fixture();data.planning!.purchases=[{id:5,name:'Wakacje',amount:1200,low:900,high:1800,due_date:'2027-01-15',account_id:2,account_name:'Alior',category_id:3,status:'PLANNED',notes:'',reserve_id:4,saved:100,monthly_required:300,version:7,reserve_version:2}];
    show(<BudgetPurchases data={data} reload={reload}/>);
    fireEvent.click(screen.getByRole('button',{name:'Edytuj plan zakupu: Wakacje'}));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Zapisz plan zakupu'}));
    await waitFor(()=>expect(planningApi.updatePurchase).toHaveBeenCalledWith(5,expect.objectContaining({reserve_version:2,status:'PLANNED'}),7));
  });
  it('records an actual variable bill amount with both bill and reserve versions',async()=>{
    const data=fixture();data.bills=[{id:8,title:'OC auta',account_id:2,account_name:'Alior',category_id:3,category_name:'Transport',frequency:'ONCE',amount:500,due_date:'2026-10-15',status:'UPCOMING',entry_id:null,active:true,version:4,reserve_id:4,reserve_name:'OC auta',reserve_version:2}];data.planning!.bill_catalog=data.bills;
    show(<BudgetObligations data={data} reload={reload}/>);
    fireEvent.click(screen.getByRole('button',{name:'Zapisz opłacenie'}));
    const form=within(screen.getByRole('dialog'));
    fireEvent.change(form.getByLabelText('Zapłacona kwota w PLN'),{target:{value:'480'}});
    fireEvent.click(form.getByRole('button',{name:'Zapisz opłacenie'}));
    await waitFor(()=>expect(budgetWorkspaceApi.payBill).toHaveBeenCalledWith(8,'2026-10',expect.any(String),expect.objectContaining({amount:480,version:4,reserve_version:2,request_id:expect.any(String)})));
  });
  it('saves the payday boundary and accounts used by the forecast',async()=>{
    show(<BudgetPayCycle data={fixture()} forecast={null} reload={reload}/>);
    fireEvent.change(screen.getByLabelText('Dzień początku okresu'),{target:{value:'31'}});
    fireEvent.change(screen.getByLabelText('Konto rat kredytów'),{target:{value:'2'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz ustawienia'}));
    await waitFor(()=>expect(planningApi.settings).toHaveBeenCalledWith({pay_day:31,income_id:null,spending_account_id:1,loan_account_id:2,version:2}));
  });
});

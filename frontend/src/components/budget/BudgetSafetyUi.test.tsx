import {fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {beforeEach,describe,expect,it,vi} from 'vitest';
import {budgetWorkspaceApi,type BudgetWorkspace,type BudgetEntry} from '../../api_budget_workspace';
import {reservesApi,type ReservesWorkspace} from '../../api_reserves';
import {accountsApi} from '../../api_accounts';
import BudgetRefundDialog from './BudgetRefundDialog';
import BudgetReserveFunding from './BudgetReserveFunding';
import BudgetMonthReview from './BudgetMonthReview';
import type {ReserveMonthPlan} from '../../api_planning';
vi.mock('../../api_budget_workspace',()=>({budgetWorkspaceApi:{refund:vi.fn(),get:vi.fn()}}));
vi.mock('../../api_reserves',()=>({reservesApi:{get:vi.fn(),move:vi.fn()}}));
vi.mock('../../api_accounts',()=>({accountsApi:{transfer:vi.fn()}}));
const purchase:BudgetEntry={id:9,account_id:1,account_name:'PKO',kind:'EXPENSE',amount:100,refunded:20,version:3,date:'2026-10-02',description:'LIDL',merchant:'LIDL',has_receipt:false,bill_id:null,loan_id:null,lines:[{category_id:2,category_name:'Jedzenie',amount:100,label:''}]};
const workspace:BudgetWorkspace={month:'2026-10',accounts:[{id:1,name:'PKO',balance:900,currency:'PLN'}],categories:[{id:2,name:'Jedzenie',icon:'',manual_plan:0,planned_bills:0,planned:0,spent:80,remaining:-80}],bills:[],entries:[purchase],totals:{balance:900,income:0,spent:80,planned:0,remaining_in_plan:-80,to_plan:900}};
const row:ReserveMonthPlan={reserve_id:4,name:'OC',account_id:2,account_name:'Alior',due_date:'2027-02-01',recommended:200,planned:200,funded:50,remaining:150,priority:2,version:0,reserve_version:1,active:true,automatic:true};
const reserves:ReservesWorkspace={as_of:'2026-10-03',accounts:[{id:1,name:'PKO',balance:1000,reserved:0,available:1000},{id:2,name:'Alior',balance:500,reserved:50,available:450}],categories:[{id:2,name:'Jedzenie'}],warnings:[],totals:{saved:50,remaining:750,monthly_required:200,urgent_amount:0,active:1},items:[{id:4,name:'OC',notes:'',account_id:2,account_name:'Alior',target_amount:800,saved:50,start_date:'2026-10-03',due_date:'2027-02-01',frequency:'ONCE',cycle:1,version:5,status:'ACTIVE',remaining:750,monthly_required:200,months_left:4,next_contribution_date:'2026-11-03',progress_percent:6.25,surplus:0,urgent:false,overdue:false,funded_this_month:true,movements:[]}]};
const reload=vi.fn(async()=>undefined),close=vi.fn();
const show=(node:React.ReactNode)=>render(<MemoryRouter>{node}</MemoryRouter>);
beforeEach(()=>{vi.resetAllMocks();vi.mocked(budgetWorkspaceApi.refund).mockResolvedValue({id:10});vi.mocked(reservesApi.get).mockResolvedValue(reserves);vi.mocked(reservesApi.move).mockResolvedValue({id:1,budget_entry_id:null});vi.mocked(accountsApi.transfer).mockResolvedValue({id:1});});
describe('Budget safety controls',()=>{
  it('records a partial refund linked to the purchase and previews the positive cash effect',async()=>{
    show(<BudgetRefundDialog purchase={purchase} data={workspace} reload={reload} onClose={close}/>);
    expect(screen.getByLabelText('Kwota zwrotu (PLN)')).toHaveValue(80);
    fireEvent.change(screen.getByLabelText('Kwota zwrotu (PLN)'),{target:{value:'30'}});
    expect(screen.getByText(/900,00.*930,00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Zapisz zwrot'}));
    await waitFor(()=>expect(budgetWorkspaceApi.refund).toHaveBeenCalledWith(9,expect.objectContaining({amount:30,version:3,balance_mode:'APPLY',expected_balance:900,category_id:2}),expect.any(String)));
  });
  it('links an imported refund without a second account credit',async()=>{
    vi.mocked(budgetWorkspaceApi.get).mockResolvedValue({...workspace,entries:[{...purchase,id:10,kind:'INCOME',date:'2026-10-03',amount:80,version:6}]});
    show(<BudgetRefundDialog purchase={purchase} data={workspace} reload={reload} onClose={close}/>);
    fireEvent.change(screen.getByLabelText('Data otrzymania zwrotu'),{target:{value:'2026-10-03'}});
    fireEvent.change(screen.getByLabelText('Jak uwzględnić zwrot'),{target:{value:'MATCH'}});
    fireEvent.click(screen.getByRole('button',{name:'Znajdź wpływ z banku'}));
    await screen.findByRole('option',{name:/LIDL · 80,00/});
    fireEvent.change(screen.getByLabelText('Wpływ odpowiadający zwrotowi'),{target:{value:'10'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz zwrot'}));
    await waitFor(()=>expect(budgetWorkspaceApi.refund).toHaveBeenCalledWith(9,expect.objectContaining({existing_entry_id:10,entry_version:6,balance_mode:'HISTORY'}),expect.any(String)));
  });
  it('funds the reserve with fresh versions while keeping the account balance unchanged',async()=>{
    show(<BudgetReserveFunding row={row} mode="ADD" reload={reload} onClose={close}/>);
    await screen.findByLabelText('Kwota odłożenia');
    expect(screen.getByText(/500,00.*500,00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Zapisz odłożenie'}));
    await waitFor(()=>expect(reservesApi.move).toHaveBeenCalledWith(4,expect.objectContaining({kind:'ADD',amount:150,account_id:2}),5,expect.any(String)));
    expect(accountsApi.transfer).not.toHaveBeenCalled();
  });
  it('records one transfer and earmarking with current source and target balances',async()=>{
    show(<BudgetReserveFunding row={row} mode="TRANSFER" reload={reload} onClose={close}/>);
    await screen.findByLabelText('Kwota odłożenia');
    expect(screen.getByText(/1000,00.*850,00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Zapisz przelew i odłożenie'}));
    await waitFor(()=>expect(accountsApi.transfer).toHaveBeenCalledWith(expect.objectContaining({source_account_id:1,target_account_id:2,amount:150,source_balance:1000,target_balance:500,reserve_id:4,version:5,reserve_action:'FUND'}),expect.any(String)));
    expect(reservesApi.move).not.toHaveBeenCalled();
  });
  it('shows unpaid obligations, missing funding and unverified balances before closing',()=>{
    const planning={settings:{} as NonNullable<BudgetWorkspace['planning']>['settings'],reserve_plans:[],policies:[],purchases:[],bill_catalog:[],cycle:{} as NonNullable<BudgetWorkspace['planning']>['cycle'],closing:{},month_review:{token:'review',accounts:[{id:1,name:'PKO',balance:900,reserved:0,verified_on:null}],corrections:[],unpaid_bills:[{id:1,title:'ENEA',date:'2026-10-15',amount:250}],unpaid_loans:[],missing_reserves:[row],unassigned:2,warnings:[]}};
    show(<BudgetMonthReview data={{...workspace,planning}}/>);
    expect(screen.getByText('Nie sprawdzono')).toBeInTheDocument();
    expect(screen.getByRole('link',{name:'Brak rozliczenia: ENEA'})).toHaveAttribute('href','/budget?view=bills&month=2026-10');
    expect(screen.getByRole('link',{name:'Brakuje odłożenia: OC'})).toBeInTheDocument();
    expect(within(screen.getByRole('table')).getByText('900,00 zł',{exact:false})).toBeInTheDocument();
  });
});

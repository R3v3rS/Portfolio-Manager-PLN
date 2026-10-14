import {render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {beforeEach,afterEach,expect,it,vi} from 'vitest';
import {budgetWorkspaceApi,type BudgetWorkspace} from '../../api_budget_workspace';
import BudgetDefaultPlans from './BudgetDefaultPlans';
import BudgetPlanCopy from './BudgetPlanCopy';
import ForecastMonthPlans from './ForecastMonthPlans';
import type {CashForecast} from '../../api_forecast';

vi.mock('../../api_budget_workspace',()=>({budgetWorkspaceApi:{defaultPlans:vi.fn(),saveDefaults:vi.fn(),previewCopy:vi.fn(),copyRange:vi.fn()}}));
const data={month:'2026-10',categories:[{id:1,name:'Jedzenie',manual_plan:1000,plan_source:'MONTH'},{id:2,name:'Paliwo',manual_plan:400,plan_source:'MONTH'},{id:3,name:'Prąd',manual_plan:0,monthly_reserve_managed:true}],accounts:[],bills:[],entries:[],totals:{}} as unknown as BudgetWorkspace;
beforeEach(()=>{
  vi.clearAllMocks();vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date('2026-10-13T12:00:00Z'));
  vi.mocked(budgetWorkspaceApi.defaultPlans).mockResolvedValue({month:'2026-10',items:[
    {category_id:1,name:'Jedzenie',parent_id:null,managed:false,amount:1000,start_month:'2026-10',revision:'food',history:[]},
    {category_id:2,name:'Paliwo',parent_id:null,managed:false,amount:null,start_month:null,revision:'fuel',history:[]},
    {category_id:3,name:'Prąd',parent_id:null,managed:true,amount:null,start_month:null,revision:'power',history:[]},
  ]});
});
afterEach(()=>vi.useRealTimers());
it('keeps zero as a default and skips blank and media inputs',async()=>{
  const reload=vi.fn(async()=>{});
  render(<MemoryRouter><BudgetDefaultPlans data={data} reload={reload}/></MemoryRouter>);
  const food=await screen.findByLabelText('Domyślny limit: Jedzenie');
  fireEvent.change(food,{target:{value:'0'}});
  expect(screen.queryByLabelText('Domyślny limit: Prąd')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Zapisz plan domyślny (1)'}));
  await waitFor(()=>expect(budgetWorkspaceApi.saveDefaults).toHaveBeenCalledWith('2026-10',[{category_id:1,amount:0,revision:'food'}]));
  expect(budgetWorkspaceApi.copyRange).not.toHaveBeenCalled();
});
it('requires a reviewed range copy and retains existing exceptions by default',async()=>{
  vi.mocked(budgetWorkspaceApi.previewCopy).mockResolvedValue({source:'2026-10',start:'2026-11',months:12,replace:false,copied:1,skipped:1,token:'reviewed',rows:[
    {month:'2026-11',category_id:1,name:'Jedzenie',action:'ADD',amount:1000,previous:0},
    {month:'2026-12',category_id:1,name:'Jedzenie',action:'KEEP',amount:1000,previous:0},
  ]});
  render(<MemoryRouter><BudgetPlanCopy data={data} reload={vi.fn(async()=>{})} onClose={vi.fn()}/></MemoryRouter>);
  expect(screen.queryByRole('button',{name:'Zapisz pokazane limity'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Pokaż podgląd'}));
  const preview=within(await screen.findByRole('region',{name:'Podgląd kopiowania'}));
  expect(preview.getByText('Zachowaj wyjątek')).toBeInTheDocument();
  expect(budgetWorkspaceApi.copyRange).not.toHaveBeenCalled();
  fireEvent.click(preview.getByRole('button',{name:'Zapisz pokazane limity'}));
  await waitFor(()=>expect(budgetWorkspaceApi.copyRange).toHaveBeenCalledWith({source:'2026-10',start:'2026-11',months:12,replace:false,category_ids:[1,2]},'reviewed',expect.any(String)));
});
it('invalidates the preview when the range or replace option changes',async()=>{
  vi.mocked(budgetWorkspaceApi.previewCopy).mockResolvedValue({source:'2026-10',start:'2026-11',months:12,replace:false,copied:1,skipped:0,token:'old',rows:[]});
  render(<MemoryRouter><BudgetPlanCopy data={data} reload={vi.fn(async()=>{})} onClose={vi.fn()}/></MemoryRouter>);
  fireEvent.click(screen.getByRole('button',{name:'Pokaż podgląd'}));
  await screen.findByRole('button',{name:'Zapisz pokazane limity'});
  fireEvent.change(screen.getByLabelText('Liczba miesięcy'),{target:{value:'3'}});
  expect(screen.queryByRole('button',{name:'Zapisz pokazane limity'})).not.toBeInTheDocument();
  expect(budgetWorkspaceApi.copyRange).not.toHaveBeenCalled();
});
it('labels inherited estimates and preserves a visible monthly zero in forecast details',()=>{
  const forecast={as_of:'2026-10-13',end_date:'2027-10-13',month_plans:[{month:'2026-11',ordinary_limit:1000,ordinary_remaining:1000,income:3000,bills:100,loans:0,reserves:200,reserve_payments:0,investments:100,scenario:false,categories:[
    {category_id:1,name:'Jedzenie',amount:1000,source:'ESTIMATE',source_month:'2026-10'},
    {category_id:2,name:'Paliwo',amount:0,source:'MONTH',source_month:'2026-11'},
  ]}]} as unknown as CashForecast;
  render(<MemoryRouter><ForecastMonthPlans data={forecast}/></MemoryRouter>);
  expect(screen.getByText('Zawiera szacunkowe limity')).toBeInTheDocument();
  expect(screen.getByText('Szacunek · 2026-10')).toBeInTheDocument();
  expect(screen.getByText('Miesięczny · 2026-11')).toBeInTheDocument();
  expect(screen.getByText('0,00 zł')).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Edytuj ten miesiąc'})).toHaveAttribute('href','/budget?view=plan&month=2026-11');
});

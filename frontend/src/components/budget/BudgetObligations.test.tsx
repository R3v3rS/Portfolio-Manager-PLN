import {render,screen,fireEvent,within,waitFor} from '@testing-library/react';
import {MemoryRouter,useLocation} from 'react-router-dom';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {budgetWorkspaceApi,type BudgetWorkspace} from '../../api_budget_workspace';
import BudgetObligations from './BudgetObligations';

vi.mock('../../api_budget_workspace',()=>({budgetWorkspaceApi:{payBill:vi.fn()}}));
beforeEach(()=>{vi.clearAllMocks();vi.useRealTimers();});
afterEach(()=>vi.useRealTimers());
function Location(){const location=useLocation();return <output data-testid="location">{location.search}</output>;}
it('opens the requested bill with an existing payment selected, without booking it',async()=>{
  vi.useFakeTimers({toFake:['Date']});
  vi.setSystemTime(new Date('2026-10-13T12:00:00Z'));
  const data={month:'2026-10',entries:[],accounts:[{id:1,name:'PKO',balance:900}],categories:[{id:1,name:'Prąd'}],bills:[
    {id:1,title:'Czynsz',category_id:1,account_id:1,account_name:'PKO',amount:500,status:'PAID',frequency:'MONTHLY',due_date:'2026-10-10'},
    {id:2,title:'ENEA',category_id:1,account_id:1,account_name:'PKO',amount:180,status:'UPCOMING',frequency:'MONTHLY',due_date:'2026-10-15',payment_candidates:[{id:7,description:'Płatność ENEA',date:'2026-10-12',amount:180,version:1,category_ids:[1]}]},
  ]} as unknown as BudgetWorkspace;
  render(<MemoryRouter initialEntries={['/budget?view=bills&month=2026-10&bill=2']}><BudgetObligations data={data} reload={vi.fn(async()=>{})}/><Location/></MemoryRouter>);
  const dialog=within(await screen.findByRole('dialog'));
  expect(dialog.getByLabelText('Powiązanie z istniejącą transakcją')).toHaveValue('7');
  expect(dialog.getByText(/istniejący plan: ENEA/)).toBeInTheDocument();
  expect(budgetWorkspaceApi.payBill).not.toHaveBeenCalled();
  await waitFor(()=>expect(screen.getByTestId('location')).toHaveTextContent('?view=bills&month=2026-10'));
  fireEvent.click(dialog.getByRole('button',{name:'Anuluj'}));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

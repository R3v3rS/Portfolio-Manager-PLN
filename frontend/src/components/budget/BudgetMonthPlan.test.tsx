import {it,expect,vi} from 'vitest';
import {fireEvent,render,screen,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import BudgetMonthPlan from './BudgetMonthPlan';
import type {BudgetWorkspace} from '../../api_budget_workspace';
vi.mock('./BudgetObligations',()=>({BillPayment:({bill}:{bill:{title:string}})=><div role="dialog">Rozliczenie: {bill.title}</div>}));
it('opens a planned bill directly from the unified month plan',()=>{
 const data={month:'2026-10',totals:{income:1000,spent:0,to_plan:700},categories:[],entries:[],bills:[{id:1,title:'Energia',due_date:'2026-10-20',account_name:'Konto',status:'PENDING',amount:180,reserve_id:2,reserve_covered:180}],planning:{loans:[],reserve_plans:[],month_plan:[{kind:'BILLS',name:'Rachunki',planned:180,done:0,remaining:180,month_cost:0}]}} as unknown as BudgetWorkspace;
 render(<MemoryRouter><BudgetMonthPlan data={data} reload={vi.fn()}/></MemoryRouter>);
 fireEvent.click(within(screen.getByRole('row',{name:/Rachunki/})).getByRole('button',{name:'Pokaż plan'}));
 expect(screen.getByText(/Finansowanie z rezerwy/)).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Rozlicz zaplanowany rachunek'}));
 expect(screen.getByRole('dialog')).toHaveTextContent('Energia');
});

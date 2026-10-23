import { useState } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BudgetCategory, BudgetWorkspace } from '../../api_budget_workspace';
import BudgetNavigation from './BudgetNavigation';
import BudgetCategoryPlanTable from './BudgetCategoryPlanTable';
import BudgetFundingProgress from './BudgetFundingProgress';
import BudgetSpendingBreakdown from './BudgetSpendingBreakdown';
import BudgetTransactions from './BudgetTransactions';
import { categoryAllocation, categoryProgress } from './budgetPlanPresentation';
import { setBudgetManagement, useBudgetDraftGuard, useBudgetMode } from './budgetMode';

const root:BudgetCategory={id:1,name:'Dom',icon:'House',manual_plan:300,planned:300,planned_bills:0,spent:40,actual_spent:40,remaining:260};
const child:BudgetCategory={...root,id:2,parent_id:1,name:'Wyposażenie',path:'Dom › Wyposażenie',manual_plan:300,spent:40,remaining:260};
const empty:BudgetCategory={...root,id:3,parent_id:1,name:'Inne zakupy',path:'Dom › Inne zakupy',manual_plan:0,planned:0,spent:0,remaining:0};
const data:BudgetWorkspace={month:'2026-01',accounts:[],categories:[root,child,empty],bills:[],entries:[],totals:{balance:0,income:0,planned:300,spent:40,remaining_in_plan:260,to_plan:0}};
beforeEach(()=>{cleanup();setBudgetManagement(false);});
afterEach(()=>{cleanup();vi.restoreAllMocks();setBudgetManagement(false);});

function ModePage({active='plan'}:{active?:string}){
  const {management}=useBudgetMode();
  const [value,setValue]=useState('100');
  useBudgetDraftGuard(management&&value!=='100');
  return <><BudgetNavigation active={active} month="2026-01"/>{management&&<label>Roboczy limit<input value={value} onChange={e=>setValue(e.target.value)}/></label>}</>;
}
describe('Budget browsing and management',()=>{
  it('starts in browsing, retains daily actions, and keeps management across budget routes',()=>{
    render(<MemoryRouter initialEntries={['/budget']}><Routes><Route path="/budget" element={<ModePage/>}/><Route path="/budget/reserves" element={<ModePage active="reserves"/>}/></Routes></MemoryRouter>);
    expect(screen.queryByRole('link',{name:'Ustawienia'})).not.toBeInTheDocument();
    expect(screen.getByText('Dodaj / Importuj')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Włącz zarządzanie'}));
    fireEvent.click(screen.getByRole('link',{name:'Rezerwy'}));
    expect(screen.getByRole('button',{name:'Zakończ zarządzanie'})).toBeInTheDocument();
    expect(screen.getByRole('link',{name:'Rezerwy'})).toHaveAttribute('aria-current','page');
    fireEvent.click(screen.getByRole('button',{name:'Zakończ zarządzanie'}));
    expect(screen.queryByLabelText('Roboczy limit')).not.toBeInTheDocument();
  });
  it('protects dirty changes on leaving management, following a link, and changing the month',()=>{
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);
    setBudgetManagement(true);
    render(<MemoryRouter initialEntries={['/budget']}><ModePage/></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Roboczy limit'),{target:{value:'125'}});
    fireEvent.click(screen.getByRole('button',{name:'Zakończ zarządzanie'}));
    expect(screen.getByLabelText('Roboczy limit')).toHaveValue('125');
    fireEvent.click(screen.getByRole('link',{name:'Rezerwy'}));
    fireEvent.click(screen.getByRole('button',{name:'Następny miesiąc'}));
    expect(confirm).toHaveBeenCalledTimes(3);
    const unload=new Event('beforeunload',{cancelable:true});window.dispatchEvent(unload);expect(unload.defaultPrevented).toBe(true);
    fireEvent.change(screen.getByLabelText('Roboczy limit'),{target:{value:'100'}});
    fireEvent.click(screen.getByRole('button',{name:'Zakończ zarządzanie'}));
    expect(confirm).toHaveBeenCalledTimes(3);
    expect(screen.getByRole('button',{name:'Włącz zarządzanie'})).toBeInTheDocument();
  });
  it('opens one selected limit and explains that the whole parent amount is already assigned',()=>{
    const setPlan=vi.fn();
    render(<MemoryRouter><BudgetCategoryPlanTable data={data} editing busy={false} drafts={{1:'300',2:'300',3:'0'}} setDraft={vi.fn()} onSave={setPlan} onReset={vi.fn()} onEdit={vi.fn()} onAdd={vi.fn()} reload={async()=>{}}/></MemoryRouter>);
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Szczegóły kategorii: Dom'}));
    const breakdown=within(screen.getByLabelText('Podział planu: Dom'));
    expect(breakdown.getByText('Nieprzypisana część planu').parentElement).toHaveTextContent('0,00');
    expect(screen.getByText(/Bez własnej kwoty.*0,00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Zmień limit: Dom › Wyposażenie'}));
    expect(screen.getAllByRole('spinbutton')).toHaveLength(1);
    expect(screen.getByLabelText('Limit: Dom › Wyposażenie')).toBeInTheDocument();
    expect(setPlan).not.toHaveBeenCalled();
  });
});

describe('Plan presentation and spending drilldown',()=>{
  it('counts child allocations and direct payments once with money rounded to cents',()=>{
    const parent={...root,planned:410.03,direct_planned_bills:60.01};
    expect(categoryAllocation(parent,[parent,{...child,planned:300.01},empty])).toEqual({assigned:300.01,directPayments:60.01,unassigned:50.01});
    expect(categoryAllocation(root,[root,child,empty]).unassigned).toBe(0);
  });
  it('distinguishes saved media money from actual purchases and clips overrun tracks',()=>{
    const media={...root,planned:100,actual_spent:0,spent:60,remaining:40,plan_details:{ordinary_planned:0,ordinary_spent:0,ordinary_remaining:0,payments_planned:100,payments_pending:0,media_remaining:40,ordinary_over:0}};
    expect(categoryProgress(media)).toMatchObject({spent:0,funding:100,percent:60,fundedAmount:60,fundingAmount:40});
    const over=categoryProgress({...root,planned:30,spent:40,actual_spent:40});
    expect(over.spent).toBe(100);expect(over.percent).toBeGreaterThan(100);
    expect(categoryProgress({...root,planned:0}).percent).toBeNull();
  });
  it('does not invent a percentage for voluntary zero funding and keeps extra savings explicit',()=>{
    const {rerender}=render(<BudgetFundingProgress name="Awaryjne" planned={0} funded={500}/>);
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByText(/brak obowiązkowej wpłaty/)).toBeInTheDocument();
    rerender(<BudgetFundingProgress name="Awaryjne" planned={100} funded={150}/>);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow','100');
    expect(screen.getByText(/150% planu.*ponad plan/)).toBeInTheDocument();
  });
  it('drills down a split purchase and reports only its selected-category items after refunds',()=>{
    const entries:BudgetWorkspace['entries']=[{id:1,account_id:1,account_name:'Bank',kind:'EXPENSE',amount:100,date:'2026-01-10',description:'Zakup mieszany',merchant:null,has_receipt:false,bill_id:null,loan_id:null,lines:[{category_id:2,category_name:'Wyposażenie',label:'Lampa',amount:40},{category_id:4,category_name:'Jedzenie',label:'Zakupy',amount:60}]},{id:2,account_id:1,account_name:'Bank',kind:'REFUND',amount:10,date:'2026-01-11',description:'Zwrot lampy',merchant:null,has_receipt:false,bill_id:null,loan_id:null,lines:[{category_id:2,category_name:'Wyposażenie',label:'Zwrot',amount:10}]}];
    const workspace={...data,entries,categories:[...data.categories,{...root,id:4,name:'Jedzenie'}]};
    render(<MemoryRouter initialEntries={['/budget']}><Routes><Route path="/budget" element={<BudgetSpendingBreakdown data={workspace}/>}/></Routes></MemoryRouter>);
    expect(screen.getByRole('link',{name:/Dom/})).toHaveAttribute('href','/budget?view=entries&month=2026-01&category=1');
    cleanup();
    render(<MemoryRouter initialEntries={['/budget?view=entries&category=1']}><BudgetTransactions data={workspace}>{entry=><div key={entry.id}>{entry.description}</div>}</BudgetTransactions></MemoryRouter>);
    const summary=within(document.querySelector('.budget-transaction-summary')! as HTMLElement);
    expect(summary.getByText(/Wydatki po zwrotach/)).toHaveTextContent('30,00');
    expect(screen.getByText('Zakup mieszany')).toBeInTheDocument();
    expect(screen.getByLabelText('Kategoria transakcji')).toHaveValue('1');
  });
});

import {setBudgetManagement} from './budgetMode';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { it, expect, vi, beforeEach } from 'vitest';
import { budgetWorkspaceApi, type BudgetWorkspace } from '../../api_budget_workspace';
import BudgetCategoryPayments from './BudgetCategoryPayments';

vi.mock('../../api_budget_workspace',()=>({budgetWorkspaceApi:{createBill:vi.fn(),updateBill:vi.fn(),payBill:vi.fn()}}));
beforeEach(()=>{setBudgetManagement(true);vi.clearAllMocks();});
it('lists child bills inside the parent limit and prefills the category of a new bill', async () => {
  const data={month:'2026-10',accounts:[{id:1,name:'PKO',balance:2000,currency:'PLN'}],categories:[{id:1,name:'Mieszkanie',manual_plan:1000,planned:1000,planned_bills:600,remaining:1000},{id:2,name:'Czynsz',parent_id:1,selection_label:'Mieszkanie › Czynsz'}],
    bills:[{id:3,title:'Czynsz październik',category_id:2,account_id:1,account_name:'PKO',due_date:'2026-10-10',amount:600,status:'UPCOMING'}],entries:[],totals:{},
  } as unknown as BudgetWorkspace;
  vi.mocked(budgetWorkspaceApi.createBill).mockResolvedValue({id:5});
  render(<MemoryRouter><BudgetCategoryPayments category={data.categories[0]} data={data} reload={vi.fn(async()=>{})}/></MemoryRouter>);
  expect(screen.getByText('Czynsz październik')).toBeInTheDocument();
  expect(within(screen.getByLabelText('Podział limitu: Mieszkanie')).getByText('400,00 zł')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Dodaj rachunek do: Mieszkanie'}));
  const form=within(screen.getByRole('dialog'));
  expect(form.getByLabelText('Kategoria')).toHaveValue('1');
  fireEvent.change(form.getByLabelText('Nazwa'),{target:{value:'Przegląd mieszkania'}});
  fireEvent.change(form.getByLabelText('Kwota w PLN'),{target:{value:'100'}});
  fireEvent.change(form.getByLabelText('Kategoria'),{target:{value:'2'}});
  fireEvent.click(form.getByRole('button',{name:'Zapisz zobowiązanie'}));
  await waitFor(()=>expect(budgetWorkspaceApi.createBill).toHaveBeenCalledWith(expect.objectContaining({category_id:2,account_id:1,amount:100,title:'Przegląd mieszkania'})));
  expect(budgetWorkspaceApi.payBill).not.toHaveBeenCalled();
});

import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { it, expect } from 'vitest';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import BudgetTransactions from './BudgetTransactions';

it('filters a shared parent, groups days and keeps refunds and transfers out of income', () => {
  const data = { month:'2026-10', accounts:[{id:1,name:'PKO'},{id:2,name:'Alior'}], categories:[{id:3,name:'Transport'},{id:4,name:'Paliwo',parent_id:3}],
    entries:[{id:1,date:'2026-10-03',description:'Stacja paliw',kind:'EXPENSE',amount:100,account_id:1,account_name:'PKO',lines:[{category_id:4,category_name:'Paliwo',label:'Paliwo'}]},
      {id:2,date:'2026-10-03',description:'Zwrot paliwa',kind:'REFUND',amount:20,account_id:1,account_name:'PKO',lines:[{category_id:4,category_name:'Paliwo',label:''}]},
      {id:3,date:'2026-10-02',description:'Pensja',kind:'INCOME',amount:1000,account_id:1,account_name:'PKO',lines:[]}],
    bank_transfers:[{id:1,date:'2026-10-02',description:'Na rezerwę',amount:50,source_account_id:1,target_account_id:2,source_name:'PKO',target_name:'Alior'}],
  } as unknown as BudgetWorkspace;
  render(<MemoryRouter><BudgetTransactions data={data}>{entry=><article key={entry.id}>{entry.description}</article>}</BudgetTransactions></MemoryRouter>);
  expect(screen.getAllByRole('region')).toHaveLength(2);
  expect(within(screen.getByRole('region',{name:'Transakcje: 2026-10-03'})).getByRole('heading')).toHaveTextContent('80,00');
  expect(screen.getByText('Na rezerwę')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Więcej filtrów i zapisane widoki'));
  fireEvent.change(screen.getByLabelText('Kategoria transakcji'),{target:{value:'3'}});
  expect(screen.getByText('Stacja paliw')).toBeInTheDocument();
  expect(screen.queryByText('Pensja')).not.toBeInTheDocument();
  expect(screen.queryByText('Na rezerwę')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Szukaj transakcji'),{target:{value:'zwrot'}});
  expect(screen.queryByText('Stacja paliw')).not.toBeInTheDocument();
  expect(screen.getByText('Zwrot paliwa')).toBeInTheDocument();
});

it('opens one linked expense and lets the user return to all transactions',()=>{
  const data={month:'2026-10',accounts:[],categories:[],entries:[{id:76,description:'Płatność wody',date:'2026-10-19',amount:374.2,kind:'EXPENSE',account_id:2,account_name:'Alior',lines:[]},{id:77,description:'Telefon',date:'2026-10-19',amount:55,kind:'EXPENSE',account_id:2,account_name:'Alior',lines:[]}]} as unknown as BudgetWorkspace;
  render(<MemoryRouter initialEntries={['/budget?view=entries&month=2026-10&entry_id=76']}><BudgetTransactions data={data}>{entry=><article key={entry.id}>{entry.description}</article>}</BudgetTransactions></MemoryRouter>);
  expect(screen.getByText('Płatność wody')).toBeInTheDocument();expect(screen.queryByText('Telefon')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Pokaż wszystkie transakcje'}));expect(screen.getByText('Telefon')).toBeInTheDocument();
});

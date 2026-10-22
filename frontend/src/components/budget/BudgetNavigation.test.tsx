import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { it, expect } from 'vitest';
import BudgetNavigation from './BudgetNavigation';

it('preserves the selected month in all main views and import shortcuts', () => {
  render(<MemoryRouter initialEntries={['/budget/accounts?month=2026-09']}><BudgetNavigation active="accounts" current/></MemoryRouter>);
  expect(screen.getByRole('link',{name:'Plan miesiąca'})).toHaveAttribute('href','/budget?view=plan&month=2026-09');
  expect(screen.getByRole('link',{name:'Konta'})).toHaveAttribute('aria-current','page');
  fireEvent.click(screen.getByRole('button',{name:'Następny miesiąc'}));
  expect(screen.getByLabelText('Miesiąc budżetu')).toHaveValue('2026-10');
  expect(screen.getByRole('link',{name:'Rezerwy'})).toHaveAttribute('href','/budget/reserves?month=2026-10');
  expect(screen.getByRole('link',{name:'Ustawienia'})).toHaveAttribute('href','/budget?view=settings&month=2026-10');
  fireEvent.click(screen.getByText('Dodaj / Importuj'));
  expect(screen.getByRole('link',{name:'Wyciąg bankowy'})).toHaveAttribute('href','/budget/imports?tab=csv&month=2026-10');
});

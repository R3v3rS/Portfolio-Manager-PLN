import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Layout from './Layout';
import { portfolioApi } from '../api';

vi.mock('../api', () => ({ portfolioApi: { list: vi.fn() } }));

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({ addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  });
  vi.mocked(portfolioApi.list).mockResolvedValue({ portfolios: [] } as Awaited<ReturnType<typeof portfolioApi.list>>);
});
afterEach(() => { cleanup(); document.body.style.overflow = ''; });

const show = (path: string) => render(
  <MemoryRouter initialEntries={[path]}><Layout><h1>Treść strony</h1></Layout></MemoryRouter>
);

describe('Layout navigation', () => {
  it('shows imports within the budget and uses its breadcrumb', () => {
    show('/budget/imports');
    expect(within(screen.getByRole('navigation', { name: 'Nawigacja główna' })).getByRole('link', { name: 'Importy i paragony' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('navigation', { name: 'Ścieżka nawigacji' })).toHaveTextContent('Importy i paragony');
  });
  it('opens the forecast as a budget section with the matching breadcrumb',()=>{
    show('/budget/forecast');
    const nav=screen.getByRole('navigation',{name:'Nawigacja główna'});
    expect(within(nav).getByRole('link',{name:'Prognoza pieniędzy'})).toHaveAttribute('aria-current','page');
    expect(screen.getByRole('navigation',{name:'Ścieżka nawigacji'})).toHaveTextContent('Prognoza pieniędzy');
  });
  it('shows accounts and reserves as budget sections with the current location',()=>{
    show('/budget/accounts');
    const nav=screen.getByRole('navigation',{name:'Nawigacja główna'});
    expect(within(nav).getByRole('link',{name:'Konta i przelewy'})).toHaveAttribute('aria-current','page');
    expect(within(nav).getByRole('link',{name:'Rezerwy na wydatki'})).toHaveAttribute('href','/budget/reserves');
    expect(screen.getByRole('navigation',{name:'Ścieżka nawigacji'})).toHaveTextContent('Konta i przelewy');
  });
  it('groups investments and shows the current tools location', () => {
    show('/admin/symbol-mapping');
    const nav = screen.getByRole('navigation', { name: 'Nawigacja główna' });
    expect(within(nav).getByRole('link', { name: 'Historia transakcji' })).toHaveAttribute('href', '/transactions');
    expect(within(nav).getByRole('link', { name: 'Mapowanie symboli' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('navigation', { name: 'Ścieżka nawigacji' })).toHaveTextContent('Narzędzia');
    expect(screen.getByRole('navigation', { name: 'Ścieżka nawigacji' })).toHaveTextContent('Mapowanie symboli');
  });

  it('uses the portfolio name in the breadcrumb after loading', async () => {
    vi.mocked(portfolioApi.list).mockResolvedValue({
      portfolios: [{ id: 1, name: 'IKE', children: [{ id: 2, name: 'Dywidendowe' }] }],
    } as Awaited<ReturnType<typeof portfolioApi.list>>);
    show('/portfolio/2');
    expect(await screen.findByText('Dywidendowe')).toHaveAttribute('aria-current', 'page');
  });

  it('closes the mobile drawer with Escape and restores focus', () => {
    show('/transactions');
    const opener = screen.getByRole('button', { name: 'Otwórz menu' });
    fireEvent.click(opener);
    const dialog = screen.getByRole('dialog', { name: 'Menu nawigacji' });
    expect(within(dialog).getByRole('link', { name: 'Historia transakcji' })).toHaveAttribute('aria-current', 'page');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});

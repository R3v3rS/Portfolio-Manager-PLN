import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TransferModal from './TransferModal';
import { portfolioApi } from '../../api';
import { budgetApi } from '../../api_budget';
import { vi } from 'vitest';

vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api');
  return {
    ...actual,
    portfolioApi: {
      deposit: vi.fn(),
      withdraw: vi.fn(),
      transferCash: vi.fn(),
      getJobStatus: vi.fn(),
    },
  };
});

vi.mock('../../api_budget', async () => {
  const actual = await vi.importActual<typeof import('../../api_budget')>('../../api_budget');
  return {
    ...actual,
    budgetApi: {
      withdrawFromPortfolio: vi.fn(),
    },
  };
});

const mockedPortfolioApi = vi.mocked(portfolioApi);
const mockedBudgetApi = vi.mocked(budgetApi);

describe('TransferModal', () => {
  const baseProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSuccess: vi.fn(),
    portfolioId: 10,
    budgetAccounts: [{ id: 5, name: 'Konto Główne', balance: 1000, currency: 'PLN' }],
    maxCash: 2000,
    subPortfolios: [
      { id: 11, name: 'Sub A', account_type: 'STANDARD', current_cash: 1200, total_deposits: 2000, savings_rate: 0, parent_portfolio_id: 10, children: [] },
      { id: 12, name: 'Sub B', account_type: 'STANDARD', current_cash: 500, total_deposits: 1000, savings_rate: 0, parent_portfolio_id: 10, children: [] },
    ],
  } as const;

  beforeEach(() => {
    mockedPortfolioApi.deposit.mockResolvedValue({} as never);
    mockedPortfolioApi.withdraw.mockResolvedValue({} as never);
    mockedPortfolioApi.transferCash.mockResolvedValue({ job_id: 'job-1' } as never);
    mockedPortfolioApi.getJobStatus.mockResolvedValue({ status: 'done' } as never);
    mockedBudgetApi.withdrawFromPortfolio.mockResolvedValue({} as never);
  });

  it('submits DEPOSIT transaction', async () => {
    const user = userEvent.setup();
    render(<TransferModal {...baseProps} />);

    await user.type(screen.getByRole('spinbutton'), '350');
    await user.click(screen.getByRole('button', { name: 'Wpłać' }));

    expect(mockedPortfolioApi.deposit).toHaveBeenCalledWith(expect.objectContaining({ portfolio_id: 10, amount: 350 }));
  });

  it('submits WITHDRAW to selected budget account', async () => {
    const user = userEvent.setup();
    render(<TransferModal {...baseProps} />);

    await user.click(screen.getByRole('button', { name: 'Wypłata' }));
    await user.selectOptions(screen.getAllByRole('combobox')[1], '5');
    await user.type(screen.getByRole('spinbutton'), '250');
    await user.click(screen.getByRole('button', { name: 'Wypłać' }));

    expect(mockedBudgetApi.withdrawFromPortfolio).toHaveBeenCalledWith(10, 5, 250, 'Wypłata z portfela inwestycyjnego', expect.any(String));
  });

  it('shows validation error for invalid internal transfer amount and does not call API', async () => {
    const user = userEvent.setup();
    render(<TransferModal {...baseProps} />);

    await user.click(screen.getByRole('button', { name: 'Sub→Sub' }));
    await user.selectOptions(screen.getAllByRole('combobox')[0], '11');
    await user.selectOptions(screen.getAllByRole('combobox')[1], '12');
    await user.type(screen.getByRole('spinbutton'), '0');
    await user.click(screen.getByRole('button', { name: 'Wykonaj przelew' }));

    expect(mockedPortfolioApi.transferCash).not.toHaveBeenCalled();
  });

  it('shows processing status for successful internal transfer job', async () => {
    const user = userEvent.setup();
    render(<TransferModal {...baseProps} />);

    await user.click(screen.getByRole('button', { name: 'Sub→Sub' }));
    await user.selectOptions(screen.getAllByRole('combobox')[0], '11');
    await user.selectOptions(screen.getAllByRole('combobox')[1], '12');
    await user.type(screen.getByRole('spinbutton'), '200');
    await user.click(screen.getByRole('button', { name: 'Wykonaj przelew' }));

    expect(await screen.findByText('Przeliczanie historii zakończone.')).toBeInTheDocument();
  });
});

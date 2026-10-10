import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TransactionModal from './TransactionModal';
import { portfolioApi } from '../../api';
import { vi } from 'vitest';

vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api');
  return {
    ...actual,
    portfolioApi: {
      buy: vi.fn(),
      addDividend: vi.fn(),
      addBond: vi.fn(),
      updateSavingsRate: vi.fn(),
      addSavingsInterest: vi.fn(),
    },
  };
});

const mockedPortfolioApi = vi.mocked(portfolioApi);

describe('TransactionModal', () => {
  it('renders buy form fields for STANDARD portfolio and submits BUY transaction', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onSuccess = vi.fn();

    mockedPortfolioApi.buy.mockResolvedValue({} as never);

    render(
      <TransactionModal
        isOpen
        onClose={onClose}
        onSuccess={onSuccess}
        portfolioId={12}
        portfolioType="STANDARD"
        holdings={[]}
      />
    );

    await user.type(screen.getByRole('combobox'), 'aapl');
    await user.type(screen.getAllByRole('spinbutton')[0], '5');
    await user.type(screen.getAllByRole('spinbutton')[1], '120');
    await user.click(screen.getByRole('checkbox', { name: 'Konto PLN w XTB (Prowizja FX 0.5%)' }));

    expect(screen.getAllByRole('spinbutton')[2]).toHaveValue(3);

    await user.click(screen.getByRole('button', { name: 'Zatwierdź' }));

    expect(mockedPortfolioApi.buy).toHaveBeenCalledWith(
      expect.objectContaining({
        portfolio_id: 12,
        ticker: 'AAPL',
        quantity: 5,
        price: 120,
        commission: 3,
        auto_fx_fees: true,
      }),expect.any(String)
    );
    expect(onSuccess).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('switches to dividend mode and submits dividend transaction', async () => {
    const user = userEvent.setup();

    mockedPortfolioApi.addDividend.mockResolvedValue({} as never);

    render(
      <TransactionModal
        isOpen
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        portfolioId={7}
        portfolioType="STANDARD"
        holdings={[{ ticker: 'MSFT' } as never]}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Dywidenda' }));
    await user.selectOptions(screen.getByRole('combobox'), 'MSFT');
    await user.type(screen.getByRole('spinbutton'), '55');
    await user.click(screen.getByRole('button', { name: 'Zatwierdź' }));

    expect(mockedPortfolioApi.addDividend).toHaveBeenCalledWith(
      expect.objectContaining({ portfolio_id: 7, ticker: 'MSFT', amount: 55 })
    );
  });
  it('keeps the purchase identifier when retrying and changes it for a different purchase',async()=>{
    const user=userEvent.setup();
    const alertSpy=vi.spyOn(window,'alert').mockImplementation(()=>undefined);
    const consoleSpy=vi.spyOn(console,'error').mockImplementation(()=>undefined);
    mockedPortfolioApi.buy.mockReset();
    mockedPortfolioApi.buy.mockRejectedValueOnce(new Error('Brak odpowiedzi')).mockResolvedValue({} as never);
    render(<TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} portfolioId={12} portfolioType="STANDARD" holdings={[]}/>);
    await user.type(screen.getByRole('combobox'),'ABC');
    await user.type(screen.getAllByRole('spinbutton')[0],'1');
    await user.type(screen.getAllByRole('spinbutton')[1],'100');
    await user.click(screen.getByRole('button',{name:'Zatwierdź'}));
    await user.click(screen.getByRole('button',{name:'Zatwierdź'}));
    const requests=mockedPortfolioApi.buy.mock.calls;
    expect(requests[0][1]).toBeTruthy();expect(requests[1][1]).toBe(requests[0][1]);
    await user.clear(screen.getAllByRole('spinbutton')[1]);
    await user.type(screen.getAllByRole('spinbutton')[1],'110');
    await user.click(screen.getByRole('button',{name:'Zatwierdź'}));
    expect(requests[2][1]).not.toBe(requests[0][1]);
    expect(document.querySelector('input[type="date"]')).toHaveAttribute('max',new Date().toLocaleDateString('sv-SE'));
    alertSpy.mockRestore();consoleSpy.mockRestore();
  });

  it('handles API error with user feedback and reenables submit button', async () => {
    const user = userEvent.setup();
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);

    mockedPortfolioApi.buy.mockRejectedValue(new Error('Błąd zapisu transakcji'));

    render(
      <TransactionModal
        isOpen
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        portfolioId={3}
        portfolioType="STANDARD"
        holdings={[]}
      />
    );

    await user.type(screen.getByRole('combobox'), 'TSLA');
    await user.type(screen.getAllByRole('spinbutton')[0], '1');
    await user.type(screen.getAllByRole('spinbutton')[1], '100');
    await user.click(screen.getByRole('button', { name: 'Zatwierdź' }));

    expect(await screen.findByRole('button', { name: 'Zatwierdź' })).toBeEnabled();
    expect(alertSpy).toHaveBeenCalledWith('Błąd zapisu transakcji');

    alertSpy.mockRestore();
  });
});

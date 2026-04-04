import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SellModal from './SellModal';
import { portfolioApi } from '../../api';
import { vi } from 'vitest';

vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api');
  return {
    ...actual,
    portfolioApi: {
      sell: vi.fn(),
    },
  };
});

const mockedPortfolioApi = vi.mocked(portfolioApi);

describe('SellModal', () => {
  const holding = {
    ticker: 'NVDA',
    quantity: 10,
    average_buy_price: 80,
    current_price: 95,
    currency: 'USD',
    sub_portfolio_id: 4,
  } as never;

  it('renders prefilled sell form and submits SELL request', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onSuccess = vi.fn();

    mockedPortfolioApi.sell.mockResolvedValue({} as never);

    render(
      <SellModal
        isOpen
        onClose={onClose}
        onSuccess={onSuccess}
        portfolioId={2}
        holding={holding}
      />
    );

    expect(screen.getByRole('heading', { name: 'Sprzedaj NVDA' })).toBeInTheDocument();
    expect(screen.getAllByRole('spinbutton')[0]).toHaveValue(10);

    await user.clear(screen.getAllByRole('spinbutton')[0]);
    await user.type(screen.getAllByRole('spinbutton')[0], '4');
    await user.clear(screen.getAllByRole('spinbutton')[1]);
    await user.type(screen.getAllByRole('spinbutton')[1], '120');
    await user.click(screen.getByRole('button', { name: 'Sprzedaj Akcje' }));

    expect(mockedPortfolioApi.sell).toHaveBeenCalledWith(
      expect.objectContaining({
        portfolio_id: 2,
        ticker: 'NVDA',
        quantity: 4,
        price: 120,
        sub_portfolio_id: 4,
      })
    );
    expect(onClose).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
  });

  it('shows disabled state during request and handles server error', async () => {
    const user = userEvent.setup();
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);

    let rejectRequest: ((error: Error) => void) | undefined;
    mockedPortfolioApi.sell.mockReturnValue(
      new Promise((_, reject) => {
        rejectRequest = reject;
      }) as never
    );

    render(
      <SellModal
        isOpen
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        portfolioId={2}
        holding={holding}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Sprzedaj Akcje' }));
    expect(screen.getByRole('button', { name: 'Przetwarzanie...' })).toBeDisabled();

    rejectRequest?.(new Error('Sell failed on server'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sprzedaj Akcje' })).toBeEnabled();
    });
    expect(alertSpy).toHaveBeenCalledWith('Sell failed on server');

    alertSpy.mockRestore();
  });

  it('returns null when modal is closed', () => {
    const { container } = render(
      <SellModal
        isOpen={false}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        portfolioId={2}
        holding={holding}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });
});

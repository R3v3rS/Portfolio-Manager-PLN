import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AccountOverview from './AccountOverview';
import type { Portfolio, PortfolioValue } from '../../types';
import type { PPKSummary } from '../../services/ppkCalculator';

const value: PortfolioValue = {portfolio_value:1000,cash_value:1000,holdings_value:0,total_dividends:0,total_interest:20,open_positions_result:0,total_result:20,total_result_percent:2};
describe('Purposeful account summaries', () => {
  it('separates the recorded savings balance from interest estimates', () => {
    render(<AccountOverview portfolio={{account_type:'SAVINGS',savings_rate:3} as Portfolio} value={{...value,live_interest:10}} summary={null} transactions={[]} price={null}/>);
    expect(screen.getByRole('heading')).toHaveTextContent('990,00');
    expect(screen.getByText('Zapisane odsetki').closest('article')).toHaveTextContent('20,00');
    expect(screen.getByText('Odsetki od ostatniego rozliczenia').closest('article')).toHaveTextContent('10,00');
    expect(screen.queryByText('Otwarte pozycje')).not.toBeInTheDocument();
  });
  it('labels gross PPK fund performance separately from the estimated withdrawal value', () => {
    render(<AccountOverview portfolio={{account_type:'PPK'} as Portfolio} value={value} summary={{totalCurrentValue:1200,totalNetValue:950,totalProfit:200,totalPurchaseValue:1000,totalUnits:10,averagePrice:100} as PPKSummary} transactions={[{id:1,portfolio_id:1,date:'2026-01-01',employee_units:6,employer_units:4,price_per_unit:100}]} price={{price:120,date:'2020-01-01'}}/>);
    expect(screen.getByRole('heading')).toHaveTextContent('1200,00');
    expect(screen.getByText('Twoje wpłaty').closest('article')).toHaveTextContent('600,00');
    expect(screen.getByText('Wpłaty pracodawcy').closest('article')).toHaveTextContent('400,00');
    expect(screen.getByText('Wynik funduszu brutto').closest('article')).toHaveTextContent('200,00');
    expect(screen.getByText('Szacunkowa kwota zwrotu').closest('article')).toHaveTextContent('950,00');
    expect(screen.getByRole('status')).toHaveTextContent('starsza niż 7 dni');
    expect(screen.queryByText('Dywidendy')).not.toBeInTheDocument();
  });
});

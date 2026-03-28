import type { FlattenedPortfolio, Portfolio } from '../types';

export const flattenPortfolios = (portfolios: Portfolio[]): FlattenedPortfolio[] => {
  return portfolios.flatMap((portfolio) => {
    const parentEntry: FlattenedPortfolio = {
      ...portfolio,
      parent_name: null,
    };

    const childrenEntries: FlattenedPortfolio[] = (portfolio.children ?? []).map((child) => ({
      ...child,
      parent_name: portfolio.name,
    }));

    return [parentEntry, ...childrenEntries];
  });
};

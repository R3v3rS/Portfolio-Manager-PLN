import { createApiClient } from './apiConfig';

export type AssetClass = 'stocks' | 'bonds' | 'ppk' | 'savings' | 'cash';
export type AssetAllocation = Record<AssetClass, number>;
export type GoalPlan = {
  name: string; description: string; target_amount: number; target_date: string;
  monthly_contribution: number; annual_return: number; portfolio_ids: number[];
  target_allocation: AssetAllocation | null;
};
export type InvestmentGoal = GoalPlan & {
  id: number; is_archived: boolean; current_value: number | null; allocation: AssetAllocation;
  portfolio_names: string[]; warnings: string[]; overlapping_goals: string[];
};
export type GoalPortfolio = { id: number; name: string; account_type: string; parent_portfolio_id: number | null; value: number | null; warnings: string[] };
export type GoalsWorkspace = { goals: InvestmentGoal[]; portfolios: GoalPortfolio[]; as_of: string };
const client = createApiClient('/investment-goals');
export const goalsApi = {
  workspace: () => client.get<GoalsWorkspace>(''),
  create: (plan: GoalPlan) => client.post<{ id: number }>('', plan),
  update: (id: number, plan: GoalPlan) => client.put<{ id: number }>(`/${id}`, plan),
  archive: (id: number, archived: boolean) => client.put(`/${id}/archive`, { archived }),
};

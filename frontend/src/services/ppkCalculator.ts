export interface PPKTransaction {
  id: number;
  portfolio_id: number;
  date: string;
  units_purchased: number;
  price_per_unit: number;
  employee_contribution: number;
  employer_contribution: number;
}

const SCALE = 1_000_000n;
const TAX_BPS = 1900n;
const EMPLOYER_WEIGHT_BPS = 7000n;

const toScaled = (value: number): bigint => BigInt(Math.round(value * Number(SCALE)));
const fromScaled = (value: bigint): number => Number(value) / Number(SCALE);

export const calculateTotalUnits = (transactions: PPKTransaction[]): number => {
  const total = transactions.reduce((sum, tx) => sum + toScaled(tx.units_purchased), 0n);
  return fromScaled(total);
};

export const calculateAveragePrice = (transactions: PPKTransaction[]): number => {
  const totalUnits = transactions.reduce((sum, tx) => sum + toScaled(tx.units_purchased), 0n);
  if (totalUnits === 0n) return 0;

  const weighted = transactions.reduce((sum, tx) => {
    const units = toScaled(tx.units_purchased);
    const price = toScaled(tx.price_per_unit);
    return sum + (units * price) / SCALE;
  }, 0n);

  return fromScaled((weighted * SCALE) / totalUnits);
};

export const calculateWeightedContribution = (transactions: PPKTransaction[]): number => {
  const employee = transactions.reduce((sum, tx) => sum + toScaled(tx.employee_contribution), 0n);
  const employer = transactions.reduce((sum, tx) => sum + toScaled(tx.employer_contribution), 0n);
  const weightedEmployer = (employer * EMPLOYER_WEIGHT_BPS) / 10000n;
  return fromScaled(employee + weightedEmployer);
};

export const calculateNetProfit = (transactions: PPKTransaction[], currentPrice: number): number => {
  const totalUnits = toScaled(calculateTotalUnits(transactions));
  const current = toScaled(currentPrice);
  const currentValue = (totalUnits * current) / SCALE;
  const contribution = toScaled(calculateWeightedContribution(transactions));
  const profit = currentValue - contribution;
  if (profit <= 0n) return fromScaled(profit);
  const tax = (profit * TAX_BPS) / 10000n;
  return fromScaled(profit - tax);
};

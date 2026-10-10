import { describe, expect, it } from 'vitest';
import { allocateDeposit, emptyAllocation, projectGoal, requiredMonthly } from './goalModel';

describe('Investment goal projections', () => {
  it('uses real monthly dates and adds payments after growth, without a partial final payment', () => {
    const result = projectGoal(1000,100,0,'2026-04-15','2026-01-31');
    expect(result.points.map(p => p.date)).toEqual(['2026-01-31','2026-02-28','2026-03-31','2026-04-15']);
    expect(result.final).toBe(1200);
    expect(result.paidIn).toBe(200);
    expect(requiredMonthly(1000,2000,0,'2026-04-15','2026-01-31')).toBe(500);
  });
  it('uses annual effective growth, including the final partial period', () => {
    const result = projectGoal(1000,0,10,'2027-01-01','2026-01-01');
    expect(result.final).toBeCloseTo(1000 * 1.1 ** (365 / 365.2425), 6);
    expect(projectGoal(1000,0,-10,'2027-01-01','2026-01-01').final).toBeLessThan(1000);
  });
  it('the calculated contribution reaches the goal within cent rounding', () => {
    const monthly = requiredMonthly(3000,50000,4,'2030-10-02','2026-10-02')!;
    expect(projectGoal(3000,monthly,4,'2030-10-02','2026-10-02').final).toBeGreaterThanOrEqual(50000);
    expect(projectGoal(3000,monthly-.01,4,'2030-10-02','2026-10-02').final).toBeLessThan(50000);
  });
  it('handles past deadlines and targets reached without further contributions', () => {
    expect(projectGoal(1000,100,0,'2025-01-01','2026-01-01').points).toEqual([{date:'2026-01-01',value:1000}]);
    expect(requiredMonthly(1000,2000,0,'2026-01-15','2026-01-01')).toBeNull();
    expect(requiredMonthly(2000,1000,0,'2026-01-15','2026-01-01')).toBe(0);
  });
});

describe('Deposit allocation based on user targets', () => {
  it('uses new capital to fill underweight categories without selling', () => {
    const rows = allocateDeposit({...emptyAllocation(), stocks:800,cash:200},{...emptyAllocation(), stocks:50,bonds:50},200);
    expect(rows.find(row => row.key==='stocks')?.amount).toBe(0);
    expect(rows.find(row => row.key==='bonds')?.amount).toBe(200);
    expect(rows.find(row => row.key==='stocks')?.after).toBe(800);
    expect(rows.reduce((sum,row) => sum+row.after,0)).toBe(1200);
  });
  it('preserves every cent on an empty portfolio and rounds without losing capital', () => {
    const rows = allocateDeposit(emptyAllocation(),{stocks:33.33,bonds:33.33,ppk:33.34,savings:0,cash:0},100.01);
    expect(rows.reduce((sum,row) => sum+Math.round(row.amount*100),0)).toBe(10001);
    expect(rows.reduce((sum,row) => sum+row.afterShare,0)).toBeCloseTo(100);
    expect(allocateDeposit(emptyAllocation(),{...emptyAllocation(),cash:100},0).every(row => row.amount===0 && row.afterShare===0)).toBe(true);
  });
  it('rejects invalid totals and negative balances instead of producing false shares', () => {
    expect(() => allocateDeposit(emptyAllocation(),emptyAllocation(),100)).toThrow();
    expect(() => allocateDeposit({...emptyAllocation(),cash:-10},{...emptyAllocation(),cash:100},100)).toThrow();
  });
});

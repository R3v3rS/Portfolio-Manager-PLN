import { describe, expect, it } from 'vitest';
import type { Holding } from '../../types';
import { allocationRows } from './allocationModel';
const position = (ticker: string, value: number | null) => ({ ticker, quantity: 1, current_value: value, average_buy_price: 999, currency: 'PLN' }) as Holding;
describe('allocation', () => {
  it('aggregates duplicate instruments and uses an explicit cash denominator', () => {
    const rows = [position('ABC', 50), position('ABC', 50), position('XYZ', 100)];
    expect(allocationRows(rows, 200, 'instrument', true).rows.find(row => row.name === 'ABC')?.share).toBe(25);
    expect(allocationRows(rows, 200, 'instrument', false).rows.find(row => row.name === 'ABC')?.share).toBe(50);
  });
  it('does not substitute purchase cost for zero or missing valuation', () => {
    const result = allocationRows([position('ZERO', 0), position('MISSING', null)], 0, 'instrument', false);
    expect(result.total).toBe(0); expect(result.missing).toEqual(['MISSING']);
    expect(result.rows[0].value).toBe(0);
  });
});

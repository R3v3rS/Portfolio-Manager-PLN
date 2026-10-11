import type { PerformanceMatrix } from '../../api_charts';
export function monthlyPoints(matrix: PerformanceMatrix) {
  return Object.keys(matrix).sort().flatMap(year => Array.from({ length: 12 }, (_, index) => index).flatMap((index) => Object.prototype.hasOwnProperty.call(matrix[year], String(index + 1)) ? [{ date: `${year}-${String(index + 1).padStart(2, '0')}`, value: matrix[year][String(index + 1)] }] : []));
}

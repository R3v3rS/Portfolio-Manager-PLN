export const chartColors = { primary: '#67ded2', secondary: '#b1a1f5', positive: '#67ded2', negative: '#f28d9c', muted: '#8fa9b3', grid: '#30464e', text: '#b4c8cf' };
export const chartTooltip = { backgroundColor: '#172830', border: '1px solid #3a535e', borderRadius: 12, color: '#edf7fa', fontSize: 12 };
export const chartMoney = (value: number) => `${value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN`;
export const chartDate = (value: string) => {
  const date = new Date(value.length === 7 ? value + '-01T12:00:00' : value + 'T12:00:00');
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('pl-PL', { month: 'short', year: 'numeric', ...(value.length > 7 ? { day: 'numeric' } : {}) });
};
export function categoryColor(key: string) {
  if (key === 'Gotówka') return chartColors.muted;
  const palette = ['#67ded2', '#b1a1f5', '#e5bc70', '#80b8ef', '#df9ecd', '#91c5a6', '#eaab88', '#a6bed5'];
  let hash = 0;
  for (const letter of key) hash = (hash * 31 + letter.charCodeAt(0)) >>> 0;
  return palette[hash % palette.length];
}

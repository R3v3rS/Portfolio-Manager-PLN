export const importMoney = (n: number) => new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(n);
export const importDay = (day: string) => day ? new Date(day + 'T12:00:00').toLocaleDateString('pl-PL') : 'Sprawdź datę';
export const importToday = () => new Date().toLocaleDateString('sv-SE');

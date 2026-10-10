import { useEffect, useState } from 'react';
import { actualResultsApi, type ActualResults } from '../../api_actual_results';
import { chartMoney } from '../charts/chartTheme';
import './actualResults.css';

const amount = (value: number | null) => value === null ? '—' : chartMoney(value);
const percent = (value: number | null) => value === null ? '—' : `${value.toLocaleString('pl-PL', { maximumFractionDigits: 2 })}%`;
const monthName = (day: string) => new Date(day + 'T12:00:00').toLocaleDateString('pl-PL', { month: 'long', year: 'numeric' });
function periodStart(period: string) {
  if (period === 'all') return undefined;
  const day = new Date(); day.setDate(1); day.setMonth(day.getMonth() - (Number(period) - 1));
  return day.toLocaleDateString('sv-SE');
}

export default function ActualResultsPanel({ portfolioId, goalId, from }: { portfolioId?: number; goalId?: number; from?: string }) {
  const [period, setPeriod] = useState('all');
  const [data, setData] = useState<ActualResults>();
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const start = from ?? periodStart(period);
  useEffect(() => {
    let active = true;
    setData(undefined); setError('');
    const request = goalId !== undefined ? actualResultsApi.goal(goalId, start) : actualResultsApi.portfolio(portfolioId!, start);
    request.then(result => { if (active) setData(result); }).catch(() => { if (active) setError('Nie udało się wczytać rzeczywistych wyników.'); });
    return () => { active = false; };
  }, [portfolioId, goalId, start, retry]);
  return <section className="chart-panel actual-results" aria-label="Rzeczywiste wyniki inwestycji">
    <div className="chart-heading"><div><p className="page-eyebrow">HISTORIA OPERACJI I WYCEN</p><h2>Co faktycznie wypracował kapitał?</h2><p>{data ? `${data.from} – ${data.to} · ${data.transaction_count} operacji · PLN` : 'Wpłaty, wypłaty i wynik inwestycji w wybranym okresie.'}</p></div>{from === undefined && <div className="chart-toolbar"><label>Okres<select aria-label="Okres rzeczywistych wyników" value={period} onChange={e => setPeriod(e.target.value)}><option value="3">3 miesiące</option><option value="6">6 miesięcy</option><option value="12">1 rok</option><option value="all">Cała historia</option></select></label></div>}</div>
    {goalId !== undefined && <p className="chart-note">Historia obecnie przypisanych portfeli, również sprzed utworzenia celu. Zmiana przypisań zmienia zakres tej analizy.</p>}
    {error ? <div role="alert" className="chart-alert">{error} <button className="actual-retry" onClick={() => setRetry(value => value + 1)}>Spróbuj ponownie</button></div> : !data ? <p className="chart-empty" role="status">Analizowanie zapisanych operacji…</p> : <>
      {data.valuation_basis && <p className="chart-note">{data.valuation_basis}</p>}
      {data.warnings.length > 0 && <div className="chart-alert" role="status">{data.warnings.map(message => <p key={message}>{message}</p>)}</div>}
      {data.status !== 'unsupported' && <>
      <div className="actual-kpis"><div><span>{data.status === 'inconsistent' ? 'Wynik wymagający wyjaśnienia' : data.status === 'partial' ? 'Wynik orientacyjny w okresie' : 'Wynik w okresie'}</span><strong className={data.profit === null ? '' : data.profit < 0 ? 'actual-negative' : 'actual-positive'}>{amount(data.profit)}</strong><small>Zmiana wyceny pomniejszona o wpłaty netto</small></div><div><span>Zwrot z uwzględnieniem przepływów</span><strong>{percent(data.dietz_percent)}</strong><small>Modified Dietz · za wybrany okres</small></div><div><span>Twój wynik roczny · XIRR</span><strong>{percent(data.xirr_percent)}</strong><small>Uwzględnia daty wpłat i wypłat; minimum rok historii</small></div></div>
      <div className="actual-bridge" aria-label="Rozliczenie zmiany wartości"><div><span>Wartość początkowa</span><b>{amount(data.opening_value)}</b></div><i>+</i><div><span>Wpłaty netto</span><b>{amount(data.net_deposits)}</b></div><i>+</i><div><span>Wynik inwestycji</span><b>{amount(data.profit)}</b></div><i>=</i><div><span>Wartość końcowa</span><b>{amount(data.closing_value)}</b></div></div>
      <div className="actual-detail-grid"><dl><div><dt>Wpłaty do analizowanych portfeli</dt><dd>{amount(data.deposits)}</dd></div><div><dt>Wypłaty z analizowanych portfeli</dt><dd>{amount(data.withdrawals)}</dd></div><div><dt>Przesunięcia wewnątrz zakresu</dt><dd>{amount(data.internal_transfer_amount)}</dd></div></dl><dl><div><dt>Zaksięgowane dywidendy</dt><dd>{amount(data.dividends)}</dd></div><div><dt>Zaksięgowane odsetki</dt><dd>{amount(data.interest)}</dd></div><div><dt>Zapisane prowizje transakcyjne</dt><dd>{amount(data.recorded_commissions)}</dd></div></dl></div>
      <p className="chart-note">Dywidendy i odsetki są już częścią wyniku. Prowizje pokazują kwoty zapisane w osobnym polu; nie odejmujemy ich ponownie od zaksięgowanych wartości transakcji. Zero prowizji w tym polu nie potwierdza braku kosztów. Sparowane transfery wewnątrz analizowanych portfeli są wyłączone z wpłat i wypłat.</p>
      {data.modeled_interest !== 0 && <p className="chart-note">Końcowa wycena obejmuje także {amount(data.modeled_interest)} odsetek oszczędności naliczonych przez model aplikacji, jeszcze niezaksięgowanych.</p>}
      <details className="actual-months"><summary>Wyniki miesiąc po miesiącu · {data.positive_months} dodatnich z {data.known_months} wyliczonych</summary><div className="actual-month-highlights"><span>Najlepszy pełny miesiąc: <b>{data.best_month ? `${monthName(data.best_month.date)} · ${percent(data.best_month.return_percent)}` : '—'}</b></span><span>Najsłabszy pełny miesiąc: <b>{data.worst_month ? `${monthName(data.worst_month.date)} · ${percent(data.worst_month.return_percent)}` : '—'}</b></span></div><div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>Miesiąc</th><th>Wpłaty netto</th><th>Wynik PLN</th><th>Zwrot okresu</th><th>Wartość na koniec</th></tr></thead><tbody>{data.months.map(month => <tr key={month.date}><th>{monthName(month.date)}{month.partial_month && <small> · część miesiąca</small>}</th><td>{amount(month.net_deposits)}</td><td className={month.profit !== null && month.profit < 0 ? 'actual-negative' : 'actual-positive'}>{amount(month.profit)}</td><td>{percent(month.return_percent)}</td><td>{amount(month.closing_value)}</td></tr>)}</tbody></table></div></details>
      <details className="actual-method"><summary>Jakość danych i sposób liczenia</summary><p className="chart-note">Wyceny historyczne pochodzą z ostatniej zapisanej ceny i kursu waluty dostępnych danego dnia. Bieżąca wycena korzysta z zapisanych aktualnych cen. To wynik oparty na historii Twoich operacji; wycena otwartych pozycji pozostaje niezrealizowana. Brakujące dane pozostają puste.</p><p className="chart-note">Modified Dietz waży wpłaty i wypłaty czasem obecności kapitału, zakładając przepływy na koniec dnia. Jest przybliżeniem; duże wpłaty i wahania w trakcie miesiąca mogą wpływać na dokładność. XIRR jest roczny i wymaga co najmniej roku historii. Przy wielokrotnej zmianie znaku przepływów inwestora wynik pozostaje pusty: nie wybieramy potencjalnie jednego z kilku rozwiązań.</p><p className="chart-note">{data.reconciliation.consistent === null ? 'Kontrola bieżącego salda nie dotyczy tego okresu lub typu konta.' : data.reconciliation.consistent ? 'Bieżąca gotówka i liczba jednostek są zgodne z historią operacji.' : `Różnica gotówki: ${amount(data.reconciliation.cash_difference)}. Niezgodne pozycje: ${data.reconciliation.positions_mismatch.join(', ') || 'brak'}.`}</p><p className="chart-note">Zysk ze sprzedaży zapisany w operacjach: {amount(data.realized_profit)}. Dotyczy sprzedaży w tym okresie, również aktywów kupionych wcześniej; dlatego nie jest składnikiem, który można bezpośrednio dodać do zmiany wyceny w okresie.</p></details>
      </>}
    </>}
  </section>;
}

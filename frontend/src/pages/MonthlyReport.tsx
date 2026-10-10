import { TrendChart } from '../components/charts/ChartKit';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowUpRight, BookOpen, CalendarDays, CheckCheck, ChevronLeft, ChevronRight, Download, FileText, Printer, RefreshCw } from 'lucide-react';
import { monthlyReportApi, type MonthlyReportData } from '../api_monthly_report';
import { extractErrorMessageFromUnknown } from '../http/response';
import { outcomes as reviewLabels } from '../components/journal/journalModel';
import '../components/reports/monthlyReport.css';

const money = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(value);
const signedMoney = (value: number) => (value > 0 ? '+' : '') + money(value);
const dateText = (value: string) => new Date(value + 'T12:00:00').toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
const localMonth = () => { const day = new Date(); return `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}`; };
const validMonth = (month: string) => /^\d{4}-(0[1-9]|1[0-2])$/.test(month) && month >= '2000-01' && month <= localMonth();
const shiftMonth = (month: string, difference: number) => {
  const [year, number] = month.split('-').map(Number); const day = new Date(year, number-1+difference, 1);
  return `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}`;
};
const monthText = (month: string) => validMonth(month) ? new Date(month + '-01T12:00:00').toLocaleDateString('pl-PL', { month: 'long', year: 'numeric' }) : 'Wybierz poprawny miesiąc';
const ratio = (value: number | null) => value == null ? '—' : value.toLocaleString('pl-PL', { maximumFractionDigits: 2, minimumFractionDigits: 2 }) + '%';

export default function MonthlyReport() {
  const [params, setParams] = useSearchParams();
  const month = params.get('month') ?? shiftMonth(localMonth(), -1);
  const [data, setData] = useState<MonthlyReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true); setData(null); setError('');
    monthlyReportApi.get(month).then(result => { if (active) setData(result); })
      .catch(err => { if (active) setError(extractErrorMessageFromUnknown(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [month, retry]);
  // Changing the URL can precede the effect that clears old data. Export/print must
  // only become available when the displayed report matches the selected month.
  const current = data?.month === month ? data : null;
  const exportReport = () => {
    if (!current || loading) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(current, null, 2)], { type: 'application/json;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href=url; anchor.download=`raport-miesieczny-${current.month}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url),1000);
  };
  const changeMonth = (value: string) => { if (value) setParams({ month: value }); };
  return <div className="page-stack mr-report">
    <header className="mr-heading page-heading"><div><p className="page-eyebrow">Zamknij miesiąc z pełnym obrazem</p><h1>Raport miesięczny</h1><p className="mr-muted">Wpływy, wydatki, kapitał i decyzje — podsumowanie zapisanych danych.</p></div><div className="mr-buttons mr-no-print"><button className="mr-button" disabled={!current || loading} onClick={exportReport}><Download size={16}/>Eksport JSON</button><button className="mr-button mr-primary" disabled={!current || loading} onClick={() => window.print()}><Printer size={16}/>Drukuj / PDF</button></div></header>
    <div className="mr-period-toolbar mr-no-print"><div className="mr-month-picker"><button className="mr-button mr-icon" aria-label="Poprzedni miesiąc" disabled={!validMonth(month) || month === '2000-01'} onClick={() => changeMonth(shiftMonth(month,-1))}><ChevronLeft size={18}/></button><label>Miesiąc raportu<input type="month" value={month} min="2000-01" max={localMonth()} onChange={e => changeMonth(e.target.value)}/></label><button className="mr-button mr-icon" aria-label="Następny miesiąc" disabled={!validMonth(month) || month === localMonth()} onClick={() => changeMonth(shiftMonth(month,1))}><ChevronRight size={18}/></button></div><div className="mr-buttons"><button className="mr-button" onClick={() => changeMonth(shiftMonth(localMonth(),-1))}>Ostatni pełny miesiąc</button><button className="mr-button" disabled={loading} aria-label="Odśwież raport" onClick={() => setRetry(value => value+1)}><RefreshCw size={16}/></button></div></div>
    {loading || (data && !current) ? <p className="mr-panel mr-loading" role="status">Przygotowywanie raportu…</p> : error ? <div className="mr-error" role="alert"><h2>Nie udało się przygotować raportu</h2><p>{error}</p><button className="mr-button" onClick={() => setRetry(value => value+1)}>Spróbuj ponownie</button></div> : current && <ReportBody data={current}/>}
  </div>;
}

function ReportBody({ data }: { data: MonthlyReportData }) {
  const budget = data.budget, operations = data.investments.operations, performance = data.investments.performance;
  const largestExpense = Math.max(1, ...budget.categories.filter(row => !row.parent_id).map(row => row.spent));
  const snapshot = data.wealth.closing || data.wealth.latest;
  return <>
    <section className="mr-cover"><div><span className="mr-cover-icon"><FileText size={23}/></span><p className="page-eyebrow">Twoje finansowe podsumowanie</p><h2>{monthText(data.month)}</h2><p><CalendarDays size={15}/>{dateText(data.period.start)} – {dateText(data.period.end)}</p></div><div className="mr-cover-note"><strong>{data.period.partial ? 'Miesiąc w toku' : 'Pełny miesiąc'}</strong><p>{data.period.partial ? 'Raport obejmuje zapisane dane do dzisiaj. Budżet porównujemy z tym samym fragmentem poprzedniego miesiąca.' : 'Budżet porównujemy z całym poprzednim miesiącem.'}</p></div></section>
    <section className="mr-kpis" aria-label="Podsumowanie miesiąca">
      <article className="mr-panel"><span>Bilans budżetu</span><strong className={(budget.budget_net??budget.net)<0 ? 'mr-negative' : 'mr-positive'}>{money(budget.budget_net??budget.net)}</strong><p>Wpływy minus obciążenie miesiąca, z odłożeniami na rezerwy i ich rozliczeniem.</p><small>Zmiana względem porównywanego okresu: {signedMoney((budget.budget_net??budget.net)-(budget.previous.budget_net??budget.previous.net))}</small></article>
      <article className="mr-panel"><span>Wynik inwestycji</span><strong className={performance.profit!=null && performance.profit<0 ? 'mr-negative' : ''}>{money(performance.profit)}</strong><p>{performance.profit==null ? 'Brak pełnych, zgodnych wycen do obliczenia wyniku.' : 'Po odjęciu wpłat i dodaniu wypłat kapitału.'}</p><small>Zakres: konta maklerskie, IKE, IKZE, oszczędności, PPK i obligacje.</small>{!performance.complete && (performance.valued_count ?? 0)>0 && <small>Wynik kont z pełną wyceną: {money(performance.available_profit ?? null)} · {performance.valued_count} z {performance.items.length} kont.</small>}</article>
      <article className="mr-panel"><span>Zapisane spłaty kredytów</span><strong>{money(data.loans.paid_amount+data.loans.overpaid_amount)}</strong><p>Raty: {money(data.loans.paid_amount)} · Nadpłaty: {money(data.loans.overpaid_amount)}</p><small>Według dat zapisanych płatności.</small></article>
      <article className="mr-panel"><span>Zmiana majątku netto</span><strong>{money(data.wealth.change)}</strong><p>{data.wealth.change==null ? 'Wymaga zapisanej wyceny na obu granicach okresu.' : 'Różnica wycen całego majątku; obejmuje także wpłaty i wydatki.'}</p><small>{snapshot ? `Ostatnia wycena w okresie: ${dateText(snapshot.date)} · ${money(snapshot.net_worth)}` : 'Brak zapisanej wyceny w tym okresie.'}</small></article>
    </section>
    {data.insights.length>0 && <section className="mr-panel mr-insights"><div className="mr-section-heading"><h2>Co wynika z tego miesiąca</h2></div>{data.insights.map((item,index) => <div className={`mr-insight ${item.tone==='attention' ? 'is-attention' : ''}`} key={index}><p>{item.text}</p><Link className="mr-text-link mr-no-print" to={item.href}>{item.label}<ArrowUpRight size={14}/></Link></div>)}</section>}
    {data.warnings.length>0 && <section className="mr-data-notes" aria-label="Uwagi do danych"><h2>Jakość danych</h2><ul>{data.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul></section>}
    <section className="mr-panel"><div className="mr-section-heading"><div><p className="page-eyebrow">Zapisane stany majątku</p><h2>Majątek w czasie</h2></div></div>
      {(data.wealth.history?.length ?? 0)>0 ? <><TrendChart data={data.wealth.history!} series={[{key:'net_worth',name:'Majątek netto',area:true},{key:'total_assets',name:'Aktywa',dashed:true},{key:'total_liabilities',name:'Dług uwzględniony w majątku',dashed:true}]}/>
      <p className="mr-note">Ostatnie 12 miesięcy do końca wybranego okresu. Zmiana między pierwszym i ostatnim dostępnym zapisem: {money(data.wealth.observed_change ?? null)}. Daty na wykresie są datami rzeczywistych zapisów; nie zastępują granic raportowanego miesiąca.</p>
      {data.wealth.history!.some(point => !point.assets_breakdown) && <p className="mr-note">Starsze zapisy nie zawierają struktury aktywów. Różnica zapisanej wartości majątku może obejmować dopisane później konta, kredyty lub korekty danych; nie oznacza sama w sobie zysku ani straty inwestycyjnej.</p>}
      {snapshot?.assets_breakdown && <div className="mr-mini-stats">{Object.entries(snapshot.assets_breakdown).map(([key,value]) => <div key={key}><span>{{budget_cash:'Konta budżetowe',invest_cash:'Gotówka inwestycyjna',savings:'Oszczędności',stocks:'Akcje i ETF',bonds:'Obligacje',ppk:'PPK — szacunkowy zwrot'}[key] ?? key}</span><b>{money(value)}</b></div>)}</div>}
      {snapshot?.valuation_notes?.map(note => <p className="mr-note" key={note}>{note}</p>)}
      </> : <p className="mr-empty">Brak zapisów majątku do końca tego okresu. Nie odtwarzamy dawnych sald z dzisiejszych kwot. Kolejne otwarcia Centrum finansów zapiszą nowe obserwacje, wraz ze strukturą aktywów.</p>}
    </section>
    <section className="mr-panel"><div className="mr-section-heading"><div><p className="page-eyebrow">Domowe finanse</p><h2>Budżet miesiąca</h2></div><Link className="mr-text-link mr-no-print" to={`/budget?month=${data.month}`}>Otwórz budżet<ArrowUpRight size={14}/></Link></div><p className="mr-muted mr-comparison">Porównanie: {dateText(data.period.previous_start)} – {dateText(data.period.previous_end)} · Wpisy: {budget.entry_count} · Paragony: {budget.receipt_count}</p>
      <p>Odłożono na rezerwy: {money(budget.reserve_contributions??0)} · Zwolniono: {money(budget.reserve_released??0)} · Rozliczono przy płatnościach: {money(budget.reserve_settled??0)}. Obciążenie budżetu miesiąca: <strong>{money(budget.budget_spent??budget.expenses)}</strong>. Poniżej faktyczne wpływy i płatności.</p><div className="mr-table-wrap"><table className="mr-table"><thead><tr><th>Przepływy w PLN</th><th>Wybrany okres</th><th>Poprzedni okres</th><th>Różnica kwot</th></tr></thead><tbody>{([{ key:'income',label:'Wpływy' },{ key:'expenses',label:'Wydatki' },{ key:'net',label:'Bilans samych wpływów i płatności' }] as const).map(row => <tr key={row.key}><th>{row.label}</th><td>{money(budget[row.key])}</td><td>{money(budget.previous[row.key])}</td><td>{signedMoney(budget.changes[row.key])}</td></tr>)}</tbody></table></div>
      <div className="mr-mini-stats"><div><span>Transfery do inwestycji</span><b>{money(budget.transfer_to_investments)}</b></div><div><span>Transfery z inwestycji</span><b>{money(budget.transfer_from_investments)}</b></div><div><span>Plan wydatków na miesiąc</span><b>{money(budget.planned)}</b></div></div><p className="mr-note">Transfery przesuwają własny kapitał i nie są wydatkiem konsumpcyjnym. Plan odzwierciedla obecnie zapisane kwoty i aktywne rachunki; nie jest archiwalną wersją planu.</p>
      {!!budget.balance_checks && <p className="mr-note">Sprawdzenia sald kont: {budget.balance_checks} · Łączna korekta: {signedMoney(budget.balance_adjustments ?? 0)}. Korekty nie zwiększają wpływów ani wydatków. <Link className="mr-text-link" to="/budget/accounts">Sprawdź historię kont</Link></p>}
      <h3 className="mr-subheading">Na co poszły pieniądze</h3>{budget.categories.length ? <div className="mr-categories">{budget.categories.filter(row => !row.parent_id).map(row => <article key={row.id || 'unassigned'}><div><strong>{row.name}</strong><b>{money(row.spent)}</b></div><div className="mr-bar" aria-hidden="true"><span className={row.planned>0 && row.spent>row.planned ? 'is-over' : ''} style={{width:`${row.spent/largestExpense*100}%`}}/></div><p>{row.planned>0 ? <>Plan: {money(row.planned)} · {row.difference>=0 ? 'Pozostało' : 'Przekroczenie'}: {money(Math.abs(row.difference))}</> : 'Bez zapisanego planu w tej kategorii'}</p>{budget.categories.some(child => child.parent_id === row.id) && <div className="mr-subcategories">{(row.direct_spent ?? 0)>0 && <div><span>Ogólnie</span><b>{money(row.direct_spent ?? 0)}</b></div>}{budget.categories.filter(child => child.parent_id === row.id).map(child => <div key={child.id}><span>{child.name}<small>{child.planned>0 ? 'Plan: ' + money(child.planned) : 'Wspólny limit kategorii'}</small></span><b>{money(child.spent)}</b></div>)}</div>}</article>)}</div> : <p className="mr-empty">Brak zapisanych wydatków i planów w kategoriach tego miesiąca.</p>}
    </section>
    <section className="mr-panel"><div className="mr-section-heading"><div><p className="page-eyebrow">Kapitał i wyniki</p><h2>Inwestycje</h2></div><Link className="mr-text-link mr-no-print" to="/portfolios">Portfele<ArrowUpRight size={14}/></Link></div>
      <div className="mr-mini-stats"><div><span>Wpłaty zewnętrzne</span><b>{money(operations.deposits)}</b></div><div><span>Wypłaty zewnętrzne</span><b>{money(operations.withdrawals)}</b></div><div><span>Dywidendy zapisane</span><b>{money(operations.dividends)}</b></div><div><span>Odsetki zapisane</span><b>{money(operations.interest)}</b></div></div>
      <p className="mr-muted mr-comparison">Operacje: {operations.count} · Zakupy: {operations.buys} · Sprzedaże: {operations.sells} · Prowizje: {money(operations.commissions)}</p>
      {performance.items.length ? <div className="mr-table-wrap"><table className="mr-table"><thead><tr><th>Portfel</th><th>Początek okresu</th><th>Koniec okresu</th><th>Wynik okresu</th><th>Zwrot w okresie</th></tr></thead><tbody>{performance.items.map(item => <PortfolioReportRows key={item.id} item={item}/>)}</tbody></table></div> : <p className="mr-empty">Nie ma aktywnych portfeli do wyceny.</p>}
      <p className="mr-note">Wynik = wycena końcowa − wycena początkowa − wpłaty + wypłaty. Zwrot uwzględnia daty przepływów metodą Modified Dietz i nie jest annualizowany. Nie sumujemy procentów różnych portfeli. PPK pokazujemy brutto, obligacje po szacowanym podatku. Niepełne, nieaktualne lub niespójne wyceny nie tworzą łącznego wyniku.</p>
      <p className="mr-note">W operacjach uwzględniono też konta archiwalne; ich obecny stan nie służy do wyceny historycznej. Sparowane transfery wewnętrzne: {money(operations.internal_transfers)}. Zapisany wynik sprzedaży: {money(operations.realized_profit)} — jest elementem wyniku inwestycji, nie dodatkowym zyskiem.</p>
      {data.investments.ppk.count>0 && <div className="mr-inline-note"><h3>Wpłaty PPK zapisane w okresie</h3><p>Pracownik: <b>{money(data.investments.ppk.employee_contributions)}</b> · Pracodawca: <b>{money(data.investments.ppk.employer_contributions)}</b> · {data.investments.ppk.count} wpisów</p><small>Kwoty wynikają z zapisanej liczby jednostek i ceny zakupu. Wpłaty nie są zyskiem.</small></div>}
    </section>
    <section className="mr-panel"><div className="mr-section-heading"><div><p className="page-eyebrow">Zapisy i harmonogramy</p><h2>Kredyty</h2></div><Link className="mr-text-link mr-no-print" to="/loans">Sprawdź kredyty<ArrowUpRight size={14}/></Link></div>
      {data.loans.items.length ? <div className="mr-table-wrap"><table className="mr-table"><thead><tr><th>Kredyt</th><th>Raty z harmonogramu</th><th>Zapisane spłaty</th><th>Nadpłaty</th><th>Saldo według modelu</th></tr></thead><tbody>{data.loans.items.map(loan => <tr key={loan.id}><th><Link to={`/loans/${loan.id}`}>{loan.name}</Link><small>{loan.without_record==null ? 'Harmonogram niedostępny' : `Raty bez zapisu płatności: ${loan.without_record}`}</small></th><td>{money(loan.scheduled_amount)}<small>Raty w okresie: {loan.scheduled_count ?? '—'}</small></td><td>{money(loan.paid_amount)}<small>Zapisane płatności: {loan.paid_count}</small></td><td>{money(loan.overpaid_amount)}</td><td>{money(loan.estimated_balance)}</td></tr>)}</tbody></table></div> : <p className="mr-empty">Brak kredytów rozpoczętych do końca tego okresu.</p>}
      <p className="mr-note">Zapisane spłaty przypisujemy do daty płatności, a harmonogram do terminu raty. Brak zapisu nie oznacza zaległości bankowej. Płatności powiązane z budżetem są już ujęte w wydatkach i nie są dodawane drugi raz.</p>
    </section>
    <section className="mr-panel"><div className="mr-section-heading"><div><p className="page-eyebrow">Proces podejmowania decyzji</p><h2>Dziennik inwestora</h2></div><Link className="mr-text-link mr-no-print" to="/journal"><BookOpen size={15}/>Otwórz dziennik</Link></div><div className="mr-mini-stats"><div><span>Wpisy z datą w okresie</span><b>{data.journal.entries.length}</b></div><div><span>Zapisane przeglądy</span><b>{data.journal.reviews.length}</b></div><div><span>Przeglądy do końca okresu, wg aktualnego stanu</span><b>{data.journal.due.length}</b></div></div>
      {data.journal.reviews.length>0 ? <div className="mr-reviews">{data.journal.reviews.map(review => <article key={review.id}><div><Link to={`/journal?entry=${review.entry_id}`}>{review.title}</Link><span>{dateText(review.review_date)} · {reviewLabels[review.outcome as keyof typeof reviewLabels] || review.outcome}</span></div><p>{review.notes}</p>{review.lessons && <p className="mr-lesson"><strong>Wniosek:</strong> {review.lessons}</p>}</article>)}</div> : <p className="mr-empty">W tym okresie nie zapisano przeglądów inwestycji.</p>}
      {data.journal.entries.length>0 && <div className="mr-journal-entries"><h3 className="mr-subheading">Decyzje i obserwacje z tego okresu</h3>{data.journal.entries.map(entry => <Link key={entry.id} to={`/journal?entry=${entry.id}`}><span>{entry.title}{entry.ticker && <small>{entry.ticker}</small>}</span><span>{dateText(entry.entry_date)}</span></Link>)}</div>}
    </section>
    <section className="mr-panel"><div className="mr-section-heading"><h2><CheckCheck size={20}/>Wykonane własne zadania</h2><Link className="mr-text-link mr-no-print" to="/">Centrum finansów<ArrowUpRight size={14}/></Link></div>{data.completed_tasks.length ? <ul className="mr-completed">{data.completed_tasks.map(task => <li key={task.id}><CheckCheck size={15}/><span>{task.title}</span><small>{new Date(task.completed_at).toLocaleDateString('pl-PL')}</small></li>)}</ul> : <p className="mr-empty">Brak obecnie wykonanych zadań z datą zakończenia w tym okresie.</p>}</section>
    <footer className="mr-footer"><p>Wygenerowano {new Date(data.generated_at).toLocaleString('pl-PL')}. Waluta raportu: PLN.</p><p>Raport odzwierciedla obecne zapisy, również korekty wprowadzone po zakończeniu miesiąca. Nie jest zamrożonym zestawieniem księgowym. Odsetki modelowane na kontach oszczędnościowych mogą być częścią bieżącej wyceny; zapisane odsetki pokazujemy oddzielnie.</p></footer>
  </>;
}

function PortfolioReportRows({ item }: { item: MonthlyReportData['investments']['performance']['items'][number] }) {
  return <><tr><th><Link to={`/portfolio/${item.id}`}>{item.name}</Link><small>{item.account_type}</small></th><td>{money(item.opening_value)}</td><td>{money(item.closing_value)}</td><td className={item.profit!=null && item.profit<0 ? 'mr-negative' : ''}>{money(item.profit)}{item.profit==null && item.estimated_profit!=null && <small>Orientacyjnie: {money(item.estimated_profit)} · nie wliczono do sumy</small>}</td><td>{ratio(item.return_percent)}</td></tr>{item.basis && <tr className="mr-quality-row"><td colSpan={5}>{item.basis}</td></tr>}{item.warnings.length>0 && <tr className="mr-quality-row"><td colSpan={5}><ul>{item.warnings.map(message => <li key={message}>{message}</li>)}</ul></td></tr>}</>;
}

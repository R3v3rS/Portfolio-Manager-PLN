import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CashForecast from './CashForecast';
import { forecastApi, type CashForecast as ForecastData, type ForecastKind } from '../api_forecast';

vi.mock('../api_forecast',()=>({forecastApi:{get:vi.fn(),createIncome:vi.fn(),updateIncome:vi.fn(),setIncomeActive:vi.fn(),receiveIncome:vi.fn()}}));
vi.mock('../components/charts/ChartKit',()=>({TrendChart:({data}:{data:{date:string}[]})=><div role="img" aria-label="Wykres prognozy">{data.at(-1)?.date}</div>}));

const forecast=():ForecastData=>({
  as_of:'2026-10-03',end_date:'2027-10-03',accounts:[{id:1,name:'Konto osobiste',balance:10000}],
  opening:{balance:10000,reserved:2000,available:8000},
  options:{income_percent:100,buffer:0,variable_monthly:null,default_variable_monthly:1500,excluded:[]},
  points:[{date:'2026-10-03',balance:10000,reserved:2000,available:8000},{date:'2026-11-02',balance:11500,reserved:2500,available:9000},{date:'2027-01-01',balance:15500,reserved:3000,available:12500},{date:'2027-10-03',balance:22000,reserved:3500,available:18500}],
  summaries:[30,90,365].map((days,index)=>({days,date:['2026-11-02','2027-01-01','2027-10-03'][index],
    balance:[11500,15500,22000][index],available:[9000,12500,18500][index],reserved:[2500,3000,3500][index],
    minimum:8000,minimum_date:'2026-10-03',minimum_balance:10000,first_shortfall:null,first_below_buffer:null,
    totals:{INCOME:6000,BILL:500,LOAN:1000,DAILY:1500,GOAL:500,RESERVE_ADD:1000,RESERVE_COST:500,EXPENSE:0,TRANSFER_IN:0,ADJUSTMENT:0} as Record<ForecastKind,number>})),
  events:[{key:'income:7:2026-10-10',date:'2026-10-10',scheduled_date:'2026-10-10',kind:'INCOME',title:'Wynagrodzenie',amount:6000,cash_delta:6000,reserved_delta:0,href:'/budget/forecast',detail:'100% planowanej kwoty',recorded:false},
    {key:'reserve-add:2',date:'2026-10-15',scheduled_date:'2026-10-15',kind:'RESERVE_ADD',title:'Ubezpieczenie auta',amount:500,cash_delta:0,reserved_delta:500,href:'/budget/reserves?reserve=2',detail:'Wydzielenie środków',recorded:false}],
  sources:[{key:'income:7',kind:'INCOME',name:'Wynagrodzenie',amount:6000,href:'/budget/forecast',included:true},{key:'bill:3',kind:'BILL',name:'Internet',amount:100,href:'/budget?view=bills',included:true}],
  incomes:[{id:7,name:'Wynagrodzenie',account_id:1,account_name:'Konto osobiste',amount:6000,start_date:'2026-10-10',end_date:null,frequency:'MONTHLY',active:true,version:2,next_occurrence:'2026-10-10',overdue:false,received_count:0}],
  recent_incomes:[{id:19,account_id:1,date:'2026-10-02',description:'Pensja',amount:5800},{id:20,account_id:2,date:'2026-10-02',description:'Inne konto',amount:100}],warnings:[],
});
const show=()=>render(<MemoryRouter><CashForecast/></MemoryRouter>);
beforeEach(()=>{vi.resetAllMocks();vi.mocked(forecastApi.get).mockResolvedValue(forecast());vi.mocked(forecastApi.createIncome).mockResolvedValue({id:8});vi.mocked(forecastApi.receiveIncome).mockResolvedValue({id:1,budget_entry_id:19});vi.mocked(forecastApi.updateIncome).mockResolvedValue({});vi.mocked(forecastApi.setIncomeActive).mockResolvedValue({});});

describe('Cash forecast',()=>{
  it('loads a purchase variant from its link and can restore the saved plan without writing',async()=>{
    render(<MemoryRouter initialEntries={['/budget/forecast?purchase=5&purchase_amount=900&purchase_date=2027-01-15']}><CashForecast/></MemoryRouter>);
    await waitFor(()=>expect(forecastApi.get).toHaveBeenCalledWith({purchase_id:5,purchase_amount:900,purchase_date:'2027-01-15'}));
    await screen.findByRole('heading',{name:'Planowane dochody'});
    fireEvent.click(screen.getByRole('button',{name:'Wróć do zapisanego planu'}));
    await waitFor(()=>expect(forecastApi.get).toHaveBeenLastCalledWith({}));
    expect(forecastApi.updateIncome).not.toHaveBeenCalled();
  });

  it('switches the chart to an individual account and shows its cash separately',async()=>{
    const data=forecast();data.account_forecasts=[{id:1,name:'Konto osobiste',opening:data.opening,
      points:[{date:'2026-10-03',balance:500,reserved:200,available:300},{date:'2027-01-01',balance:800,reserved:200,available:600}],
      summaries:data.summaries.map(s=>({days:s.days,date:s.date,balance:800,reserved:200,available:600,minimum:300,first_shortfall:null}))}];
    vi.mocked(forecastApi.get).mockResolvedValue(data);
    show();await screen.findByRole('heading',{name:'Planowane dochody'});
    fireEvent.change(screen.getByLabelText('Konto na wykresie'),{target:{value:'1'}});
    expect(screen.getByRole('img',{name:'Wykres prognozy'})).toHaveTextContent('2027-01-01');
    expect(screen.getByRole('heading',{name:'Konta za 90 dni'})).toBeInTheDocument();
    expect(forecastApi.get).toHaveBeenCalledTimes(1);
  });
  it('distinguishes cash from earmarks and switches the chart horizon without writing data',async()=>{
    show();await screen.findByRole('heading',{name:'Planowane dochody'});
    const cards=screen.getByRole('region',{name:'Saldo na 30, 90 i 365 dni'});
    expect(cards).toHaveTextContent(/11\s?500,00/);expect(cards).toHaveTextContent(/9\s?000,00/);
    expect(screen.getByRole('img',{name:'Wykres prognozy'})).toHaveTextContent('2027-01-01');
    fireEvent.click(within(cards).getByRole('button',{name:/Za 365 dni/}));
    expect(screen.getByRole('img',{name:'Wykres prognozy'})).toHaveTextContent('2027-10-03');
    expect(forecastApi.get).toHaveBeenCalledTimes(1);expect(forecastApi.createIncome).not.toHaveBeenCalled();expect(forecastApi.receiveIncome).not.toHaveBeenCalled();
  });

  it('applies an explicit scenario and excludes a source only from that forecast',async()=>{
    show();await screen.findByRole('heading',{name:'Planowane dochody'});
    fireEvent.change(screen.getByLabelText('Planowane dochody (%)'),{target:{value:'75'}});
    fireEvent.change(screen.getByLabelText('Codzienne wydatki / miesiąc (PLN)'),{target:{value:'1800'}});
    fireEvent.change(screen.getByLabelText('Minimalny bufor (PLN)'),{target:{value:'500'}});
    fireEvent.click(screen.getByRole('button',{name:'Przelicz prognozę'}));
    await waitFor(()=>expect(forecastApi.get).toHaveBeenLastCalledWith({income_percent:75,variable_monthly:1800,buffer:500,excluded:undefined}));
    await waitFor(()=>expect(screen.getByRole('button',{name:'Przelicz prognozę'})).toBeEnabled());
    fireEvent.click(screen.getByText('Które plany uwzględniamy?'));
    fireEvent.click(screen.getByRole('checkbox',{name:/Internet/}));
    await waitFor(()=>expect(forecastApi.get).toHaveBeenLastCalledWith({income_percent:75,variable_monthly:1800,buffer:500,excluded:'bill:3'}));
    expect(forecastApi.updateIncome).not.toHaveBeenCalled();
  });

  it('sets the cautious scenario without changing fixed payments',async()=>{
    show();await screen.findByRole('heading',{name:'Planowane dochody'});
    fireEvent.click(screen.getByRole('button',{name:'Ostrożny: dochody −20%, wydatki +20%'}));
    await waitFor(()=>expect(forecastApi.get).toHaveBeenLastCalledWith({income_percent:80,variable_monthly:1800}));
    expect(forecastApi.setIncomeActive).not.toHaveBeenCalled();
  });

  it('keeps the calendar focused on scheduled payments and lets users include daily spending',async()=>{
    const result=forecast();result.events.push({key:'daily:2026-10-04',date:'2026-10-04',scheduled_date:'2026-10-04',kind:'DAILY',title:'Codzienny limit',amount:50,cash_delta:-50,reserved_delta:0,href:'/budget',detail:'Limit rozłożony na dni',recorded:false});
    vi.mocked(forecastApi.get).mockResolvedValue(result);show();await screen.findByRole('heading',{name:'Planowane dochody'});
    expect(screen.getByRole('table')).toHaveTextContent('Wynagrodzenie');expect(screen.getByRole('table')).not.toHaveTextContent('Codzienny limit');
    fireEvent.change(screen.getByLabelText('Rodzaj przepływu'),{target:{value:''}});
    expect(screen.getByRole('table')).toHaveTextContent('Codzienny limit');
  });

  it('does not display a fabricated forecast or enable income creation without accounts',async()=>{
    const empty=forecast();empty.accounts=[];empty.incomes=[];empty.summaries=empty.summaries.map(s=>({...s,balance:null,available:null,minimum:null,minimum_balance:null}));
    vi.mocked(forecastApi.get).mockResolvedValue(empty);show();
    await screen.findByText('Najpierw dodaj aktualne salda kont.');
    expect(screen.queryByRole('img',{name:'Wykres prognozy'})).not.toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Dodaj dochód'})).toBeDisabled();
    expect(screen.getByRole('link',{name:'Dodaj konto'})).toHaveAttribute('href','/budget/accounts');
    expect(screen.getByRole('region',{name:'Saldo na 30, 90 i 365 dni'})).not.toHaveTextContent('0,00');
  });

  it('keeps the income draft and request identity when retrying an uncertain save',async()=>{
    vi.mocked(forecastApi.createIncome).mockRejectedValueOnce(new Error('Brak potwierdzenia'));
    show();await screen.findByRole('heading',{name:'Planowane dochody'});fireEvent.click(screen.getByRole('button',{name:'Dodaj dochód'}));
    fireEvent.change(screen.getByLabelText('Nazwa dochodu'),{target:{value:'Premia'}});
    fireEvent.change(screen.getByLabelText('Oczekiwana kwota netto (PLN)'),{target:{value:'1200'}});
    fireEvent.change(screen.getByLabelText('Pierwszy termin wpływu'),{target:{value:'2030-01-10'}});
    fireEvent.change(screen.getByLabelText('Powtarzalność'),{target:{value:'ONCE'}});
    fireEvent.submit(screen.getByLabelText('Nazwa dochodu').closest('form')!);await screen.findByText('Brak potwierdzenia');
    expect(screen.getByLabelText('Nazwa dochodu')).toHaveValue('Premia');
    fireEvent.submit(screen.getByLabelText('Nazwa dochodu').closest('form')!);
    await screen.findByText('Plan dochodu zapisany. Saldo konta pozostaje bez zmian.');
    const calls=vi.mocked(forecastApi.createIncome).mock.calls;
    expect(calls[0][0]).toEqual({name:'Premia',account_id:1,amount:1200,start_date:'2030-01-10',end_date:null,frequency:'ONCE'});
    expect(calls[0][1]).toBe(calls[1][1]);expect(forecastApi.receiveIncome).not.toHaveBeenCalled();
  });

  it('links a recorded income without creating another cash entry and closes before refresh failure',async()=>{
    vi.mocked(forecastApi.get).mockResolvedValueOnce(forecast()).mockRejectedValue(new Error('Błąd odczytu'));
    show();await screen.findByRole('heading',{name:'Planowane dochody'});fireEvent.click(screen.getByRole('button',{name:'Otrzymano'}));
    const choice=screen.getByLabelText('Sposób rozliczenia');expect(choice).not.toHaveTextContent('Inne konto');
    fireEvent.change(choice,{target:{value:'19'}});fireEvent.click(screen.getByRole('button',{name:'Połącz wpływ'}));
    await screen.findByRole('alert');
    expect(forecastApi.receiveIncome).toHaveBeenCalledWith(7,{occurrence_date:'2026-10-10',existing_entry_id:19},2,expect.any(String));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Odśwież dane'}));await waitFor(()=>expect(forecastApi.get).toHaveBeenCalledTimes(3));
    expect(forecastApi.receiveIncome).toHaveBeenCalledTimes(1);
  });

  it('records an actual amount using the plan version and preserves the occurrence date',async()=>{
    show();await screen.findByRole('heading',{name:'Planowane dochody'});fireEvent.click(screen.getByRole('button',{name:'Otrzymano'}));
    fireEvent.change(screen.getByLabelText('Otrzymana kwota (PLN)'),{target:{value:'5800'}});
    fireEvent.change(screen.getByLabelText('Data otrzymania'),{target:{value:'2026-10-02'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz otrzymanie'}));
    await waitFor(()=>expect(forecastApi.receiveIncome).toHaveBeenCalledWith(7,{occurrence_date:'2026-10-10',amount:5800,date:'2026-10-02'},2,expect.any(String)));
  });

  it('shows data gaps, pauses income with a version guard, and filters the calendar',async()=>{
    const result=forecast();result.warnings=['Brak pełnego harmonogramu kredytu.'];result.incomes[0].overdue=true;
    vi.mocked(forecastApi.get).mockResolvedValue(result);show();await screen.findByRole('heading',{name:'Planowane dochody'});
    expect(screen.getByText('Brak pełnego harmonogramu kredytu.')).toBeInTheDocument();expect(screen.getByText(/Miniony wpływ nie zwiększa prognozowanego salda/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Rodzaj przepływu'),{target:{value:'RESERVE_ADD'}});
    const table=screen.getByRole('table');expect(table).toHaveTextContent('Ubezpieczenie auta');expect(table).not.toHaveTextContent('Wynagrodzenie');
    fireEvent.click(screen.getByRole('button',{name:'Wstrzymaj dochód: Wynagrodzenie'}));
    await waitFor(()=>expect(forecastApi.setIncomeActive).toHaveBeenCalledWith(7,false,2));
  });

  it('shows a failed first read without substituting zero balances',async()=>{
    vi.mocked(forecastApi.get).mockRejectedValue(new Error('Nie można odczytać prognozy'));show();
    await screen.findByRole('alert');expect(screen.getByRole('alert')).toHaveTextContent('Nie można odczytać prognozy');
    expect(screen.queryByRole('region',{name:'Saldo na 30, 90 i 365 dni'})).not.toBeInTheDocument();
  });
});

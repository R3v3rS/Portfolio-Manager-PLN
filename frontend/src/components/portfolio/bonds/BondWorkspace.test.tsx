import { cleanup,fireEvent,render,screen,waitFor,within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach,beforeEach,describe,expect,it,vi } from 'vitest';
import { bondsApi,type BondPosition,type BondWorkspaceData } from '../../../api_bonds';
import BondWorkspace from './BondWorkspace';
import BondEditor from './BondEditor';
import BondOperations from './BondOperations';

vi.mock('../../../api_bonds',()=>({bondsApi:{workspace:vi.fn(),create:vi.fn(),update:vi.fn(),settle:vi.fn(),rate:vi.fn(),cancel:vi.fn(),estimate:vi.fn(),preview:vi.fn(),import:vi.fn()}}));
const bond:BondPosition={id:1,portfolio_id:3,name:'EDO test',kind:'EDO',quantity:10,remaining_quantity:10,nominal:100,purchase_price:100,principal:1000,
  purchase_date:'2025-01-01',maturity_date:'2035-01-01',interest_rate:6,current_rate:6,tax_rate:19,redemption_fee:3,fee_policy:'CAP_INTEREST',
  payout_account_id:1,forecast_enabled:false,notes:'',acquisition:'BUY',version:1,status:'ACTIVE',nominal_value:1000,cost_remaining:1000,
  accrued_interest:90,current_period_interest:30,capitalized_interest:60,pending_interest:30,estimated_interest_net:72.9,total_value:1090,
  estimated_value_net:1072.9,open_profit:90,paid_interest_net:0,early_redemption_net:1048.6,early_redemption_fee:30,warnings:[],as_of:'2026-10-03',
  periods:[{period:1,start_date:'2025-01-01',end_date:'2026-01-01',rate:6,assumed:false,gross:60,net:48.6,capitalizes:true,pays_cash:false,paid:false,complete:true},
    {period:2,start_date:'2026-01-01',end_date:'2027-01-01',rate:6,assumed:true,gross:63.6,net:51.52,capitalizes:true,pays_cash:false,paid:false,complete:false}],
  next_event:null,rates:[],events:[{id:1,kind:'BUY',date:'2025-01-01',quantity:10,period:null,net_amount:1000,notes:''}]};
const account={id:1,name:'PKO',balance:100,currency:'PLN'};
const data:BondWorkspaceData={as_of:'2026-10-03',items:[bond],summary:{nominal_value:1000,cost_remaining:1000,accrued_interest:90,estimated_interest_net:72.9,total_value:1090,cash:0,capitalized_interest:60,current_period_interest:30,paid_interest_net:0},kinds:{EDO:{label:'EDO',months:120,interval:12,capitalizes:true,coupons:false,variable:true}} as BondWorkspaceData['kinds'],events:[],forecast:[],warnings:[]};
beforeEach(()=>{vi.clearAllMocks();vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date('2026-10-03T12:00:00'));vi.mocked(bondsApi.workspace).mockResolvedValue(data);vi.mocked(bondsApi.create).mockResolvedValue({id:2});});
afterEach(()=>{cleanup();vi.useRealTimers();});
function view(){return render(<MemoryRouter initialEntries={['/portfolio/3?bond=1']}><BondWorkspace pid={3} accounts={[account]} onChanged={vi.fn()} onTransfer={vi.fn()}/></MemoryRouter>);}

describe('Bond workspace',()=>{
  it('shows accrued estimates separately from available cash and capitalization',async()=>{
    view();await screen.findByRole('heading',{name:'Obligacje pod kontrolą'});
    expect(screen.getByText(/gotówkę zwiększa dopiero zapis rzeczywistej wypłaty/)).toBeInTheDocument();
    expect(screen.getByText('Dostępna gotówka').parentElement).toHaveTextContent('0,00');
    expect(screen.getByText('Narosłe odsetki brutto').parentElement).toHaveTextContent('90,00');
    expect(screen.getByText('Już skapitalizowano').parentElement).toHaveTextContent('60,00');
    expect(bondsApi.settle).not.toHaveBeenCalled();
  });
  it('opens a position from the reminder link and filters closed purchases',async()=>{
    vi.mocked(bondsApi.workspace).mockResolvedValue({...data,items:[bond,{...bond,id:2,name:'Wykupiony zakup',status:'CLOSED',remaining_quantity:0,total_value:0}]});view();
    await screen.findByRole('button',{name:'Kalkulator wykupu'});expect(screen.queryByText('Wykupiony zakup')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Status obligacji'),{target:{value:'CLOSED'}});expect(screen.getByText('Wykupiony zakup')).toBeInTheDocument();
  });
  it('recovers a read failure without posting any financial operation',async()=>{
    vi.mocked(bondsApi.workspace).mockRejectedValueOnce(new Error('Brak połączenia'));view();await screen.findByRole('alert');
    fireEvent.click(screen.getByText('Spróbuj ponownie'));await screen.findByRole('heading',{name:'Serie i pozycje'});expect(bondsApi.create).not.toHaveBeenCalled();
  });
  it('requires funding for a cash purchase and explains opening assets',()=>{
    render(<BondEditor pid={3} cash={0} accounts={[account]} onSaved={vi.fn()} onClose={vi.fn()}/>);
    expect(screen.getByText('Zapisz zakup i warunki')).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Sposób dodania'),{target:{value:'EXISTING'}});
    expect(screen.getByText('Zapisz zakup i warunki')).toBeEnabled();expect(screen.getByText(/nie jest to dochód budżetu/)).toBeInTheDocument();
  });
  it('retries an uncertain save with the same request identifier',async()=>{
    vi.mocked(bondsApi.create).mockRejectedValueOnce(new Error('Sieć')).mockResolvedValueOnce({id:2});
    render(<BondEditor pid={3} cash={1000} accounts={[]} onSaved={vi.fn()} onClose={vi.fn()}/>);
    fireEvent.change(screen.getByLabelText('Seria / nazwa'),{target:{value:'EDO1036'}});
    fireEvent.change(screen.getByLabelText('Oprocentowanie pierwszego okresu (%)'),{target:{value:'5.35'}});
    fireEvent.click(screen.getByText('Zapisz zakup i warunki'));await screen.findByRole('alert');
    fireEvent.click(screen.getByText('Zapisz zakup i warunki'));await waitFor(()=>expect(bondsApi.create).toHaveBeenCalledTimes(2));
    expect(vi.mocked(bondsApi.create).mock.calls[0][2]).toBe(vi.mocked(bondsApi.create).mock.calls[1][2]);
  });
  it('records actual net payout and an explicitly confirmed budget transfer',async()=>{
    render(<BondOperations bond={bond} mode="SETTLE" cash={0} accounts={[account]} onSaved={vi.fn()} onClose={vi.fn()}/>);
    const dialog=screen.getByRole('dialog');
    expect(within(dialog).getByLabelText('Rzeczywiście otrzymano netto (zł)')).toHaveValue(null);
    fireEvent.change(within(dialog).getByLabelText('Rzeczywiście otrzymano netto (zł)'),{target:{value:'1050'}});
    fireEvent.click(within(dialog).getByLabelText(/Wypłata trafiła już na PKO/));
    fireEvent.click(within(dialog).getByLabelText(/Potwierdzam wykonaną operację/));
    expect(within(dialog).getByText(/PKO:/)).toHaveTextContent(/1\s?150,00/);
    fireEvent.click(within(dialog).getByText('Zapisz'));await waitFor(()=>expect(bondsApi.settle).toHaveBeenCalled());
    expect(vi.mocked(bondsApi.settle).mock.calls[0][1]).toMatchObject({net_amount:1050,transfer_to_budget:true,confirmed_actual:true,kind:'REDEEM'});
  });
  it('calculates without booking a payout',async()=>{
    vi.mocked(bondsApi.estimate).mockResolvedValue(bond);
    render(<BondOperations bond={bond} mode="CALCULATE" cash={0} accounts={[]} onSaved={vi.fn()} onClose={vi.fn()}/>);
    fireEvent.click(screen.getByText('Przelicz'));await screen.findByText('Szacowana wypłata po opłacie');
    expect(bondsApi.estimate).toHaveBeenCalledWith(bond,'2026-10-03',6);expect(bondsApi.settle).not.toHaveBeenCalled();
  });
  it('preserves the posted amount when editing conditions',()=>{
    render(<BondEditor pid={3} bond={bond} cash={0} accounts={[]} onSaved={vi.fn()} onClose={vi.fn()}/>);
    expect(screen.getByLabelText('Liczba sztuk')).toHaveAttribute('readonly');expect(screen.getByLabelText('Data zakupu')).toHaveAttribute('readonly');
  });
  it('scales a historical valuation by the quantity held on that date',async()=>{
    vi.mocked(bondsApi.estimate).mockResolvedValue({...bond,remaining_quantity:20,accrued_interest:100});
    render(<BondOperations bond={bond} mode="CALCULATE" cash={0} accounts={[]} onSaved={vi.fn()} onClose={vi.fn()}/>);
    fireEvent.click(screen.getByText('Przelicz'));await screen.findByText('Szacowana wypłata po opłacie');
    expect(screen.getByText('Narosłe odsetki brutto').parentElement).toHaveTextContent('50,00');
  });
});

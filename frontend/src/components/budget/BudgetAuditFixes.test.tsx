import {render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {describe,it,expect,vi,beforeEach} from 'vitest';
import {budgetWorkspaceApi,type BudgetWorkspace} from '../../api_budget_workspace';
import BudgetSettlementUndo from './BudgetSettlementUndo';
import {BudgetReservePlans} from './BudgetReservePlans';
import BudgetCharts from './BudgetCharts';
vi.mock('../../api_budget_workspace',()=>({budgetWorkspaceApi:{settlementPreview:vi.fn(),reverseSettlement:vi.fn()}}));
vi.mock('../charts/ChartKit',()=>({TrendChart:({data}:{data:unknown})=><pre data-testid="chart">{JSON.stringify(data)}</pre>}));
const data={month:'2026-10',accounts:[],entries:[],bills:[],categories:[],totals:{balance:0,income:0,spent:180,planned:250,remaining_in_plan:70,to_plan:0},planning:{reserve_plans:[{reserve_id:1,name:'Prąd',account_id:1,account_name:'PKO',category_id:1,monthly_amount:250,planned:250,funded:180,contributed:0,remaining:70,priority:2,version:0,reserve_version:1,due_date:'2026-10-01',recommended:250,active:true}],loans:[],policies:[],purchases:[],bill_catalog:[],settings:{},cycle:{},closing:{}},chart:[{date:'2026-10-03',cash_spent:180,budget_spent:250,cash_plan:180,budget_plan:250,daily_spent:40,daily_plan:60}]} as BudgetWorkspace;
const show=(node:React.ReactNode)=>render(<MemoryRouter>{node}</MemoryRouter>);
beforeEach(()=>vi.resetAllMocks());
describe('Budget audit corrections',()=>{
  it('does not describe media payments as money saved',()=>{
    show(<BudgetReservePlans data={data} reload={async()=>{}}/>);
    const header=document.querySelector('.bp-saving-total')!;
    expect(within(header as HTMLElement).getByText(/Wykonano plan/)).toHaveTextContent('180,00');
    expect(within(header as HTMLElement).getByText(/Dodatkowe wpłaty/)).toHaveTextContent('0,00');
    expect(within(header as HTMLElement).getByText(/Obciążenie puli mediów/)).toHaveTextContent('180,00');
  });
  it('switches between cash and budget burden using server series',()=>{
    show(<BudgetCharts data={data}/>);
    expect(screen.getByRole('heading',{name:'Tempo wybranych kategorii'})).toBeInTheDocument();
    expect(screen.getByTestId('chart')).toHaveTextContent('"spent":40');
    fireEvent.click(screen.getByRole('button',{name:'Obciążenie budżetu'}));
    expect(screen.getByTestId('chart')).toHaveTextContent('"spent":250');
    fireEvent.click(screen.getByRole('button',{name:'Faktyczne wydatki'}));
    expect(screen.getByTestId('chart')).toHaveTextContent('"spent":180');
  });
  it('shows completion of fixed costs separately from shopping pace',()=>{
    show(<BudgetCharts data={{...data,fixed_costs:{planned:773,paid:850,pending:0,over_plan:77,early_count:1,paid_count:1,count:1}}}/>);
    const summary=within(screen.getByRole('region',{name:'Stałe opłaty w miesiącu'}));
    expect(summary.getByText(/Zaplanowano/)).toHaveTextContent('773,00');
    expect(summary.getByText(/Opłacono/)).toHaveTextContent('850,00');
    expect(summary.getByText(/To wykonanie zobowiązania/)).toBeInTheDocument();
    expect(summary.getByText(/ponad plan/)).toHaveTextContent('77,00');
    expect(summary.getByRole('link')).toHaveAttribute('href','/budget?view=bills&month=2026-10');
  });
  it('previews and reverses a linked settlement without claiming a cash refund',async()=>{
    const preview={entry_id:5,entry_version:3,reserve_version:4,balance_before:900,balance_after:900,account_name:'PKO',delete_expense:false,restored_reserve:100,message:'Istniejący wydatek pozostanie w historii i saldzie.'};
    vi.mocked(budgetWorkspaceApi.settlementPreview).mockResolvedValue(preview);
    vi.mocked(budgetWorkspaceApi.reverseSettlement).mockResolvedValue({});
    const reload=vi.fn(async()=>{}),close=vi.fn();
    show(<BudgetSettlementUndo entryId={5} reload={reload} onClose={close}/>);
    await screen.findByText(preview.message);
    expect(screen.getByText(/900,00.*900,00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Potwierdź cofnięcie'}));
    await waitFor(()=>expect(budgetWorkspaceApi.reverseSettlement).toHaveBeenCalledWith(5,preview,expect.any(String)));
    expect(close).toHaveBeenCalledOnce();expect(reload).toHaveBeenCalledOnce();
  });
});

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import type { BudgetImportsWorkspace } from '../../api_budget_imports';
import type { Reserve, ReservesWorkspace } from '../../api_reserves';
import { budgetImportsApi } from '../../api_budget_imports';
import BudgetPaymentsSummary from './BudgetPaymentsSummary';
import BudgetReviewQueue from './BudgetReviewQueue';
import BudgetSummary from './BudgetSummary';
import ReserveCard from './ReserveCard';
import * as helpers from './planningHelpers';

vi.mock('../../api_budget_imports',()=>({budgetImportsApi:{get:vi.fn()}}));
const data=():BudgetWorkspace=>({month:'2030-01',accounts:[{id:1,name:'Bank',balance:1000,currency:'PLN'}],categories:[],entries:[],bills:[{id:2,title:'Telefon',amount:40,due_date:'2030-01-20',frequency:'MONTHLY',category_id:1,category_name:'Opłaty',account_id:1,account_name:'Bank',status:'PAID',entry_id:5}],
  totals:{balance:1000,income:5000,spent:40,planned:1000,to_plan:4000,remaining_in_plan:960,monthly_income_to_plan:4000,monthly_income_total:5000,monthly_income_cost:40,monthly_income_remaining_plan:960,expected_income:0},
  planning:{loans:[{id:7,name:'Sprzęt',amount:90,date:'2030-01-16',installment_month:3,paid:false,category_id:1,account_id:1}],reserve_plans:[],month_review:{accounts:[]}} as unknown as BudgetWorkspace['planning']});
const show=(node:React.ReactNode)=>render(<MemoryRouter>{node}</MemoryRouter>);
beforeEach(()=>{vi.spyOn(helpers,'planningToday').mockReturnValue('2030-01-15');vi.mocked(budgetImportsApi.get).mockResolvedValue({pending_count:0,sessions:[],receipts:[]} as unknown as BudgetImportsWorkspace);});
afterEach(()=>vi.restoreAllMocks());

describe('Shared payment state',()=>{
  it('includes an unpaid loan when all bills are already paid',()=>{
    show(<BudgetPaymentsSummary data={data()}/>);
    const panel=screen.getByLabelText('Podsumowanie rachunków i rat');
    expect(panel).toHaveTextContent('40,00');expect(panel).toHaveTextContent('90,00');
    expect(panel).toHaveTextContent('1 z 2 płatności');
    expect(screen.getByRole('link')).toHaveAttribute('href','/loans/7?installment=3');
    expect(screen.queryByText('Wszystkie płatności rozliczone')).not.toBeInTheDocument();
  });
  it('uses the actual paid loan amount and distinguishes an empty month from completed payments',()=>{
    const workspace=data();workspace.planning!.loans![0]={...workspace.planning!.loans![0],paid:true,paid_amount:95.12};
    const view=show(<BudgetPaymentsSummary data={workspace}/>);
    expect(screen.getByText('135,12 zł',{exact:false})).toBeInTheDocument();
    expect(screen.getByText('Wszystkie płatności rozliczone')).toBeInTheDocument();
    view.rerender(<MemoryRouter><BudgetPaymentsSummary data={{...workspace,bills:[],planning:undefined}}/></MemoryRouter>);
    expect(screen.getByText('Brak płatności w tym miesiącu')).toBeInTheDocument();
    expect(screen.queryByText('Wszystkie płatności rozliczone')).not.toBeInTheDocument();
  });
});

describe('One task queue',()=>{
  it('shows an existing-payment match once, without a second funding reminder for the same reserve',async()=>{
    const workspace=data();workspace.bills[0]={...workspace.bills[0],status:'UPCOMING',entry_id:null,payment_candidates:[{id:6,date:'2030-01-14',description:'Telefon',amount:40,version:1}]};
    workspace.planning!.reserve_plans=[{reserve_id:3,name:'Polisa',remaining:50,active:true,account_id:1,account_name:'Bank',due_date:'2030-06-15',recommended:100,planned:100,funded:50,priority:2,version:0,reserve_version:0}];
    workspace.planning!.payment_matches=[{kind:'BILL',id:2,title:'Telefon',candidates:workspace.bills[0].payment_candidates!},{kind:'RESERVE',id:3,title:'Polisa',candidates:workspace.bills[0].payment_candidates!}];
    show(<BudgetReviewQueue data={workspace} forecast={null}/>);
    await waitFor(()=>expect(budgetImportsApi.get).toHaveBeenCalled());
    const list=within(screen.getByLabelText('Do zrobienia'));
    expect(list.getByText('Telefon')).toBeInTheDocument();
    expect(list.getByText('Sprawdź powiązanie: Polisa')).toBeInTheDocument();
    expect(list.queryByText('Odłóż: Polisa')).not.toBeInTheDocument();
    expect(list.queryByText('Sprawdź powiązanie: Telefon')).not.toBeInTheDocument();
    expect(list.getAllByRole('listitem')).toHaveLength(3);
    expect(list.getByRole('link',{name:'Powiąż płatność'})).toHaveAttribute('href','/budget?view=bills&month=2030-01&bill=2');
  });
  it('initially limits the list to three and exposes the complete filtered queue',async()=>{
    const workspace=data();workspace.planning!.loans=[];
    vi.mocked(budgetImportsApi.get).mockResolvedValue({pending_count:0,sessions:[1,2,3,4].map(id=>({id,filename:`bank-${id}.csv`,status:'PENDING'})),receipts:[]} as unknown as BudgetImportsWorkspace);
    show(<BudgetReviewQueue data={workspace} forecast={null}/>);
    await screen.findByRole('button',{name:'Pokaż wszystkie (4)'});
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    fireEvent.click(screen.getByRole('button',{name:'Pokaż wszystkie (4)'}));
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    fireEvent.change(screen.getByLabelText('Rodzaj spraw'),{target:{value:'PAYMENT'}});
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  });
  it('does not report an all-clear while imports are unavailable',async()=>{
    const workspace=data();workspace.planning!.loans=[];
    vi.mocked(budgetImportsApi.get).mockRejectedValue(new Error('Offline'));
    show(<BudgetReviewQueue data={workspace} forecast={null}/>);
    expect(await screen.findByRole('status')).toHaveTextContent('Nie udało się odczytać stanu importów');
    expect(screen.getByText(/Stan importów nie został potwierdzony/)).toBeInTheDocument();
  });
});

describe('Folded details preserve key context',()=>{
  it('keeps the main amounts and expected income visible while calculations are folded',()=>{
    const workspace=data();workspace.totals.expected_income=1000;
    show(<BudgetSummary data={workspace} forecast={null} failed={false}/>);
    const income=screen.getByLabelText('Wolne z przychodów miesiąca');
    expect(within(income).getByText(/Plan uwzględnia oczekiwane wpływy/).closest('details')).toBeNull();
    const explanation=within(income).getByText('Jak to policzono?').closest('details')!;
    expect(explanation).not.toHaveAttribute('open');
    fireEvent.click(within(income).getByText('Jak to policzono?'));
    expect(explanation).toHaveAttribute('open');
    expect(within(explanation).getByText('Dochody otrzymane i oczekiwane')).toBeInTheDocument();
  });
  it('separates missing monthly funding from the remaining whole target without duplicating actions',()=>{
    const item={id:3,name:'Polisa',account_id:1,account_name:'Bank',status:'ACTIVE',saved:120,target_amount:600,remaining:480,progress_percent:20,monthly_required:100,months_left:5,due_date:'2030-06-15',frequency:'ONCE',movements:[],notes:'Opis celu',month_statement:{month:'2030-01',planned:100,funded:20,remaining:80,extra:0,added:20,payments:0}} as unknown as Reserve;
    const context={as_of:'2030-01-15',accounts:[{id:1,name:'Bank'}],categories:[{id:1,name:'Opłaty'}]} as ReservesWorkspace;
    const action=vi.fn();
    show(<ReserveCard item={item} data={context} month="2030-01" selected={false} management={false} disabled={false} onAction={action} onArchive={vi.fn()} onUndo={vi.fn()}/>);
    expect(screen.getByText('Jeszcze do odłożenia w miesiącu').parentElement).toHaveTextContent('80,00');
    expect(screen.getByText('Do celu brakuje 480,00 zł.',{exact:false})).toBeInTheDocument();
    const details=screen.getByText('Szczegóły rezerwy').closest('details')!;
    expect(details).not.toHaveAttribute('open');
    expect(screen.getAllByRole('button',{name:'Odłóż środki'})).toHaveLength(1);
    fireEvent.click(screen.getByRole('button',{name:'Odłóż środki'}));
    expect(action).toHaveBeenCalledWith('ADD',item);
    fireEvent.click(screen.getByText('Szczegóły rezerwy'));
    expect(details).toHaveAttribute('open');
    expect(screen.getByRole('button',{name:'Zwolnij'})).toBeInTheDocument();
  });
});

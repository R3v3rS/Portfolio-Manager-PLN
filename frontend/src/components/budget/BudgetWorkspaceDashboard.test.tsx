import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BudgetWorkspaceDashboard from './BudgetWorkspaceDashboard';
import { budgetWorkspaceApi, type BudgetWorkspace } from '../../api_budget_workspace';

vi.mock('./BudgetCharts',()=>({default:()=>null}));
vi.mock('../../api_budget_workspace',()=>({budgetWorkspaceApi:{get:vi.fn(),defaultPlans:vi.fn(),setPlan:vi.fn(),updateEntry:vi.fn(),createEntry:vi.fn(),createCategory:vi.fn(),updateCategory:vi.fn(),applyEntryBalance:vi.fn(),receiptUrl:(id:number)=>`/receipt/${id}`}}));
const data:BudgetWorkspace={month:'2026-10',accounts:[{id:2,name:'Konto osobiste',balance:10000,currency:'PLN'}],
  categories:[{id:1,name:'Jedzenie',icon:'',manual_plan:0,planned_bills:0,planned:0,spent:0,remaining:0},
    {id:3,name:'Chemia',icon:'',manual_plan:0,planned_bills:0,planned:0,spent:0,remaining:0},
    {id:99,name:'Nieprzypisane',icon:'',manual_plan:0,planned_bills:0,planned:0,spent:146.8,remaining:-146.8,is_unassigned:true}],
  bills:[],entries:[{id:9,version:3,account_id:2,account_name:'Konto osobiste',kind:'EXPENSE',amount:146.8,date:'2026-10-02',description:'Zakupy LIDL',merchant:'LIDL',
    has_receipt:false,bill_id:null,loan_id:null,cash_effect:false,classification_status:'UNASSIGNED',lines:[{category_id:99,category_name:'Nieprzypisane',label:'',amount:146.8}]}],
  totals:{balance:10000,income:0,planned:0,spent:146.8,remaining_in_plan:-146.8,to_plan:10000}};
beforeEach(()=>{vi.resetAllMocks();vi.mocked(budgetWorkspaceApi.defaultPlans).mockResolvedValue({month:'2026-10',items:[]});vi.mocked(budgetWorkspaceApi.get).mockResolvedValue(data);vi.mocked(budgetWorkspaceApi.updateEntry).mockResolvedValue({id:9});});
afterEach(()=>vi.restoreAllMocks());

describe('Manual split from the import queue',()=>{
  it('hides unused categories but keeps them available through search and the checkbox',async()=>{
    vi.mocked(budgetWorkspaceApi.get).mockResolvedValue({...data,categories:data.categories.map(c=>({...c,has_activity:c.id!==3}))});
    render(<MemoryRouter initialEntries={['/budget?view=settings&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    const toggle=await screen.findByLabelText('Pokaż nieużywane kategorie');
    expect(screen.queryByRole('button',{name:'Edytuj kategorię: Chemia'})).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByRole('button',{name:'Edytuj kategorię: Chemia'})).toBeInTheDocument();
    fireEvent.click(toggle);fireEvent.change(screen.getAllByLabelText('Szukaj kategorii').at(-1)!,{target:{value:'Chemia'}});
    expect(screen.getByRole('button',{name:'Edytuj kategorię: Chemia'})).toBeInTheDocument();
  });
  it('edits descriptions without changing expense or limit records',async()=>{
    vi.mocked(budgetWorkspaceApi.updateCategory).mockResolvedValue({id:3});
    render(<MemoryRouter initialEntries={['/budget?view=settings&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button',{name:'Edytuj kategorię: Chemia'}));
    const dialog=within(screen.getByRole('dialog',{name:'Edytuj kategorię'}));
    fireEvent.change(dialog.getByLabelText('Opis i przykłady'),{target:{value:'Środki czystości do domu.'}});
    fireEvent.click(dialog.getByRole('button',{name:'Zapisz zmiany'}));
    await waitFor(()=>expect(budgetWorkspaceApi.updateCategory).toHaveBeenCalledWith(3,'Chemia',null,1,true,'Środki czystości do domu.'));
    expect(budgetWorkspaceApi.setPlan).not.toHaveBeenCalled();expect(budgetWorkspaceApi.updateEntry).not.toHaveBeenCalled();
  });
  it('keeps the plan read-only until editing is explicitly enabled',async()=>{
    render(<MemoryRouter initialEntries={['/budget?view=plan&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    const edit=await screen.findByRole('button',{name:'Edytuj limity'});
    expect(screen.queryByLabelText('Limit: Jedzenie')).not.toBeInTheDocument();
    fireEvent.click(edit);
    expect(screen.getByLabelText('Limit: Jedzenie')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Zamknij edycję limitów'}));
    expect(screen.queryByLabelText('Limit: Jedzenie')).not.toBeInTheDocument();
    expect(budgetWorkspaceApi.createEntry).not.toHaveBeenCalled();
    expect(budgetWorkspaceApi.updateEntry).not.toHaveBeenCalled();
  });
  it('applies an existing expense once and keeps the completed state when refreshing fails',async()=>{
    const confirmation=vi.spyOn(window,'confirm').mockReturnValue(true);
    vi.mocked(budgetWorkspaceApi.get).mockResolvedValueOnce(data).mockRejectedValue(new Error('Brak połączenia'));
    vi.mocked(budgetWorkspaceApi.applyEntryBalance).mockResolvedValue({id:9,version:4,cash_effect:true,applied:true,balance:9853.2});
    render(<MemoryRouter initialEntries={['/budget?view=entries&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button',{name:'Uwzględnij w saldzie: Zakupy LIDL'}));
    await waitFor(()=>expect(budgetWorkspaceApi.applyEntryBalance).toHaveBeenCalledWith(9,3,10000));
    expect(confirmation).toHaveBeenCalledWith(expect.stringContaining('146,80'));
    await screen.findByText(/Zmiana salda została zapisana/);
    expect(screen.queryByRole('button',{name:'Uwzględnij w saldzie: Zakupy LIDL'})).not.toBeInTheDocument();
    expect(budgetWorkspaceApi.createEntry).not.toHaveBeenCalled();
  });
  it('cancels applying cash without modifying the purchase',async()=>{
    vi.spyOn(window,'confirm').mockReturnValue(false);
    render(<MemoryRouter initialEntries={['/budget?view=entries&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button',{name:'Uwzględnij w saldzie: Zakupy LIDL'}));
    expect(budgetWorkspaceApi.applyEntryBalance).not.toHaveBeenCalled();
  });
  it('does not offer a second deduction for expenses already applied to cash',async()=>{
    vi.mocked(budgetWorkspaceApi.get).mockResolvedValue({...data,entries:data.entries.map(entry=>({...entry,cash_effect:true}))});
    render(<MemoryRouter initialEntries={['/budget?view=entries&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    await screen.findByText('Zakupy LIDL');
    expect(screen.queryByRole('button',{name:'Uwzględnij w saldzie: Zakupy LIDL'})).not.toBeInTheDocument();
  });
  it('explains pending income in the plan without presenting it as account cash',async()=>{
    vi.mocked(budgetWorkspaceApi.get).mockResolvedValue({...data,totals:{...data.totals,balance:1172.54,expected_income:6100,reserved:435,to_plan:2704.01}});
    render(<MemoryRouter initialEntries={['/budget?month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    const summary=within(await screen.findByRole('region',{name:'Podsumowanie miesiąca'}));
    const pending=summary.getByRole('link',{name:/Wpływy do otrzymania/});
    expect(pending).toHaveTextContent(/6\s?100,00/);
    expect(pending).toHaveAttribute('href','/budget/forecast?month=2026-10');
    expect(summary.getByText(/Saldo \+ oczekiwane wpływy − pozostałe limity/)).toBeInTheDocument();
    expect(summary.getByText(/Otrzymane wpływy są już w saldzie/)).toBeInTheDocument();
    expect(summary.getByText(/2\s?704,01/)).toBeInTheDocument();
    expect(summary.getByText(/1\s?172,54/)).toBeInTheDocument();
  });
  it('creates a child from its parent without modifying existing expenses',async()=>{
    vi.mocked(budgetWorkspaceApi.createCategory).mockResolvedValue({id:5});
    render(<MemoryRouter initialEntries={['/budget?view=plan&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button',{name:'Edytuj limity'}));
    fireEvent.click(screen.getByRole('button',{name:'Dodaj podkategorię do: Jedzenie'}));
    const dialog=within(screen.getByRole('dialog',{name:'Dodaj podkategorię'}));
    expect(dialog.getByLabelText('Kategoria główna')).toHaveValue('1');
    fireEvent.change(dialog.getByLabelText('Nazwa kategorii'),{target:{value:'Restauracje'}});
    fireEvent.click(dialog.getByRole('button',{name:'Dodaj'}));
    await waitFor(()=>expect(budgetWorkspaceApi.createCategory).toHaveBeenCalledWith('Restauracje',1,true,''));
    expect(budgetWorkspaceApi.updateEntry).not.toHaveBeenCalled();
  });

  it('edits the category with its version and parent',async()=>{
    vi.mocked(budgetWorkspaceApi.updateCategory).mockResolvedValue({id:3});
    render(<MemoryRouter initialEntries={['/budget?view=plan&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button',{name:'Edytuj limity'}));
    fireEvent.click(screen.getByRole('button',{name:'Edytuj kategorię: Chemia'}));
    const dialog=within(screen.getByRole('dialog',{name:'Edytuj kategorię'}));
    fireEvent.change(dialog.getByLabelText('Kategoria główna'),{target:{value:'1'}});
    expect(dialog.getByLabelText('Uwzględniaj w tempie codziennych wydatków')).toBeChecked();
    fireEvent.click(dialog.getByLabelText('Uwzględniaj w tempie codziennych wydatków'));
    fireEvent.click(dialog.getByRole('button',{name:'Zapisz zmiany'}));
    await waitFor(()=>expect(budgetWorkspaceApi.updateCategory).toHaveBeenCalledWith(3,'Chemia',1,1,false,''));
  });

  it('groups child spending below the root and shows paths in expense choices',async()=>{
    vi.mocked(budgetWorkspaceApi.get).mockResolvedValue({...data,categories:[
      {...data.categories[0],name:'Transport',spent:255,planned:1000,direct_spent:25},
      {...data.categories[1],name:'Paliwo',parent_id:1,selection_label:'Transport › Paliwo',spent:230,planned:600},
    ]});
    render(<MemoryRouter initialEntries={['/budget?view=plan&month=2026-10']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    expect(await screen.findByText('Podkategorie (1)')).toBeInTheDocument();
    expect(screen.getByText('Transport')).toBeInTheDocument();
    expect(screen.getByText('Paliwo')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Wydatek'}));
    expect(within(screen.getByRole('dialog')).getByRole('option',{name:'Transport › Paliwo'})).toBeInTheDocument();
  });
  it('opens the selected expense and updates categories in the same versioned record',async()=>{
    render(<MemoryRouter initialEntries={['/budget?view=entries&month=2026-10&edit_entry=9']}><BudgetWorkspaceDashboard/></MemoryRouter>);
    const form=within(await screen.findByRole('dialog',{name:'Edytuj wpis'}));
    expect(budgetWorkspaceApi.get).toHaveBeenCalledWith('2026-10');expect(form.getByLabelText('Opis')).toHaveValue('Zakupy LIDL');
    fireEvent.click(form.getByRole('button',{name:'Dodaj pozycję'}));
    fireEvent.change(form.getAllByLabelText('Kategoria')[0],{target:{value:'1'}});
    fireEvent.change(form.getAllByLabelText('Kategoria')[1],{target:{value:'3'}});
    fireEvent.change(form.getAllByLabelText('Kwota')[0],{target:{value:'100'}});
    fireEvent.change(form.getAllByLabelText('Kwota')[1],{target:{value:'46.8'}});
    fireEvent.click(form.getByRole('button',{name:'Zapisz zmiany'}));
    await waitFor(()=>expect(budgetWorkspaceApi.updateEntry).toHaveBeenCalledWith(9,expect.objectContaining({version:3,account_id:2,kind:'EXPENSE',amount:146.8,date:'2026-10-02',
      lines:[{category_id:1,amount:100,label:''},{category_id:3,amount:46.8,label:''}]})));
    expect(budgetWorkspaceApi.createEntry).not.toHaveBeenCalled();
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import InvestmentGoals from './InvestmentGoals';
import { goalsApi, type GoalsWorkspace } from '../api_goals';

vi.mock('../api_goals', () => ({ goalsApi: { workspace: vi.fn(), create: vi.fn(), update: vi.fn(), archive: vi.fn() } }));
vi.mock('../components/goals/GoalDetail', () => ({ default: ({goal,onEdit}: {goal:{name:string};onEdit:()=>void}) => <section aria-label="Szczegóły celu"><h2>{goal.name}</h2><button onClick={onEdit}>Edytuj plan</button></section> }));

const workspace: GoalsWorkspace = { as_of: '2026-10-02', goals: [], portfolios: [
  { id:1,name:'IKE',account_type:'IKE',parent_portfolio_id:null,value:1000,warnings:[] },
  { id:2,name:'Podportfel',account_type:'IKE',parent_portfolio_id:1,value:300,warnings:[] },
] };
const plan = { name:'Mieszkanie',description:'',target_amount:50000,target_date:'2031-10-02',monthly_contribution:500,annual_return:0,portfolio_ids:[1],target_allocation:null };
const goal = { ...plan,id:7,is_archived:false,current_value:1000,allocation:{stocks:700,bonds:0,ppk:0,savings:0,cash:300},portfolio_names:['IKE'],warnings:[],overlapping_goals:[] };
const show = (path='/goals') => render(<MemoryRouter initialEntries={[path]}><InvestmentGoals /></MemoryRouter>);
beforeEach(() => { vi.clearAllMocks(); vi.mocked(goalsApi.workspace).mockResolvedValue(workspace); vi.mocked(goalsApi.create).mockResolvedValue({id:7}); });
afterEach(cleanup);
async function fillNewGoal() {
  fireEvent.change(screen.getByLabelText('Nazwa celu'),{target:{value:plan.name}});
  fireEvent.change(screen.getByLabelText('Kwota celu · PLN'),{target:{value:String(plan.target_amount)}});
  fireEvent.change(screen.getByLabelText('Termin celu'),{target:{value:plan.target_date}});
  fireEvent.change(screen.getByLabelText('Miesięczna wpłata · PLN'),{target:{value:String(plan.monthly_contribution)}});
  fireEvent.click(screen.getByRole('checkbox',{name:/^IKE/}));
}
describe('Investment goals workspace', () => {
  it('saves a real plan and then loads its persisted detail', async () => {
    show(); fireEvent.click(await screen.findByRole('button',{name:'Utwórz pierwszy cel'}));
    await fillNewGoal();
    expect(screen.getByRole('checkbox',{name:/^Podportfel/})).toBeDisabled();
    vi.mocked(goalsApi.workspace).mockResolvedValue({...workspace,goals:[goal]});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz cel'}));
    await waitFor(() => expect(goalsApi.create).toHaveBeenCalledWith(plan));
    expect(await screen.findByRole('region',{name:'Szczegóły celu'})).toHaveTextContent('Mieszkanie');
    expect(await screen.findByRole('status')).toHaveTextContent('Cel zapisany');
  });
  it('rejects invalid target shares before submitting', async () => {
    show('/goals?new=1'); await screen.findByLabelText('Nazwa celu'); await fillNewGoal();
    fireEvent.click(screen.getByRole('checkbox',{name:'Chcę ustalić własne udziały kategorii'}));
    fireEvent.change(screen.getByLabelText('Akcje i ETF-y · %'),{target:{value:'50'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz cel'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('100%');
    expect(goalsApi.create).not.toHaveBeenCalled();
  });
  it('does not create the goal twice if refreshing after save fails', async () => {
    show('/goals?new=1'); await screen.findByLabelText('Nazwa celu'); await fillNewGoal();
    vi.mocked(goalsApi.workspace).mockRejectedValueOnce(new Error('offline'));
    fireEvent.click(screen.getByRole('button',{name:'Zapisz cel'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Cel został zapisany');
    expect(screen.queryByRole('button',{name:'Zapisz cel'})).not.toBeInTheDocument();
    vi.mocked(goalsApi.workspace).mockResolvedValue({...workspace,goals:[goal]});
    fireEvent.click(screen.getByRole('button',{name:'Spróbuj ponownie'}));
    expect(await screen.findByRole('region',{name:'Szczegóły celu'})).toHaveTextContent('Mieszkanie');
    expect(goalsApi.create).toHaveBeenCalledTimes(1);
  });
  it('archives and restores a goal without losing its plan', async () => {
    vi.mocked(goalsApi.workspace).mockResolvedValue({...workspace,goals:[goal]}); show();
    const archive = await screen.findByRole('button',{name:'Archiwizuj cel Mieszkanie'});
    vi.mocked(goalsApi.workspace).mockResolvedValue({...workspace,goals:[{...goal,is_archived:true}]});
    fireEvent.click(archive);
    await waitFor(() => expect(goalsApi.archive).toHaveBeenCalledWith(7,true));
    fireEvent.click(await screen.findByRole('button',{name:'Archiwum (1)'}));
    const restore = await screen.findByRole('button',{name:'Przywróć cel Mieszkanie'});
    vi.mocked(goalsApi.workspace).mockResolvedValue({...workspace,goals:[goal]}); fireEvent.click(restore);
    await waitFor(() => expect(goalsApi.archive).toHaveBeenCalledWith(7,false));
  });
});

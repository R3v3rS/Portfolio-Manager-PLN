import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BudgetCategory, BudgetWorkspace } from '../../api_budget_workspace';
import BudgetSpendingBreakdown from './BudgetSpendingBreakdown';
import * as helpers from './planningHelpers';

const category = (id:number,name:string,planned:number,spent:number):BudgetCategory => ({id,name,planned,spent,actual_spent:spent,remaining:planned-spent,manual_plan:planned,planned_bills:0,icon:''});
const workspace = (categories:BudgetCategory[]):BudgetWorkspace => ({month:'2026-01',accounts:[],categories,bills:[],
  entries:categories.map(c=>({id:c.id,account_id:1,account_name:'Bank',kind:(c.actual_spent??c.spent)<0?'REFUND':'EXPENSE',amount:Math.abs(c.actual_spent??c.spent),date:'2026-01-10',description:c.name,merchant:null,has_receipt:false,bill_id:null,loan_id:null,lines:[{category_id:c.id,category_name:c.name,label:'',amount:Math.abs(c.actual_spent??c.spent)}]})),
  totals:{balance:0,income:0,spent:0,planned:0,remaining_in_plan:0,to_plan:0}});
const show = (data:BudgetWorkspace) => render(<MemoryRouter><BudgetSpendingBreakdown data={data}/></MemoryRouter>);
beforeEach(()=>vi.spyOn(helpers,'planningToday').mockReturnValue('2026-01-31'));
afterEach(()=>vi.restoreAllMocks());

describe('Spending breakdown with consistent bar meanings',()=>{
  it('fills an exceeded small category and leaves a larger category at its actual plan percentage',()=>{
    show(workspace([category(1,'Dom',30,40),category(2,'Jedzenie',200,160)]));
    const home=within(screen.getByRole('link',{name:/Dom/}));
    expect(home.getByRole('progressbar')).toHaveAttribute('aria-valuenow','100');
    expect(home.getByRole('progressbar')).toHaveAttribute('aria-valuetext','133,3% planu');
    expect(home.getByRole('progressbar').firstChild).toHaveStyle({width:'100%'});
    expect(home.getByText(/Ponad plan/)).toHaveTextContent('10,00');
    expect(screen.getByRole('link',{name:/Dom/})).toHaveClass('is-over');
    const food=within(screen.getByRole('link',{name:/Jedzenie/}));
    expect(food.getByRole('progressbar')).toHaveAttribute('aria-valuenow','80');
    expect(food.getByRole('progressbar').firstChild).toHaveStyle({width:'80%'});
    expect(food.queryByText(/Ponad plan/)).not.toBeInTheDocument();
  });
  it('switches to shares of total expenses and removes plan overrun colors and labels',()=>{
    show(workspace([category(1,'Dom',30,40),category(2,'Jedzenie',200,160)]));
    fireEvent.click(screen.getByRole('button',{name:'Udział w wydatkach'}));
    const home=within(screen.getByRole('link',{name:/Dom/}));
    const food=within(screen.getByRole('link',{name:/Jedzenie/}));
    expect(home.getByRole('progressbar')).toHaveAttribute('aria-valuenow','20');
    expect(home.getByRole('progressbar').firstChild).toHaveStyle({width:'20%'});
    expect(home.getByText('20% wydatków')).toBeInTheDocument();
    expect(food.getByRole('progressbar')).toHaveAttribute('aria-valuenow','80');
    expect(screen.getByRole('link',{name:/Dom/})).not.toHaveClass('is-over');
    expect(screen.queryByText(/Ponad plan/)).not.toBeInTheDocument();
  });
  it('does not pretend an unplanned purchase has a calculable percentage',()=>{
    show(workspace([category(1,'Drobne',0,15)]));
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByText('Bez zaplanowanej kwoty')).toBeInTheDocument();
    expect(screen.getByText(/Wydatek bez planu/)).toHaveTextContent('15,00');
  });
  it('uses budget execution for limits and separates purchases funded from earlier reserves',()=>{
    const media={...category(1,'Media',100,80),actual_spent:200,reserve_settled:120};
    show(workspace([media]));
    const card=within(screen.getByRole('link',{name:/Media/}));
    expect(card.getByRole('progressbar')).toHaveAttribute('aria-valuenow','80');
    expect(card.getByText(/Wykonanie planu:/)).toHaveTextContent('80,00');
    expect(card.getByText('200,00 zł',{exact:false})).toBeInTheDocument();
    expect(card.queryByText(/Ponad plan/)).not.toBeInTheDocument();
  });
  it('explains the missing part of the total when smaller categories are folded',()=>{
    show(workspace(Array.from({length:9},(_,i)=>category(i+1,`Kategoria ${i+1}`,100,i+1))));
    expect(screen.getAllByRole('link')).toHaveLength(7);
    expect(screen.getByText(/Pokazano 7 z 9/)).toHaveTextContent('Pozostałe kategorie: 3,00');
    expect(screen.getByText('45,00 zł',{exact:false})).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Wszystkie kategorie (9)'}));
    expect(screen.getAllByRole('link')).toHaveLength(9);
    expect(screen.queryByText(/Pokazano 7 z/)).not.toBeInTheDocument();
  });
  it('keeps refunds and unrelated months out of the wrong totals or percentages',()=>{
    const data=workspace([category(1,'Dom',100,100),category(2,'Transport',100,-50)]);
    data.entries.push({...data.entries[0],id:99,date:'2025-12-12',amount:900,lines:[{category_id:1,category_name:'Dom',label:'',amount:900}]});
    show(data);
    expect(screen.getByText('50,00 zł',{selector:'.budget-ranking-total strong',exact:false})).toBeInTheDocument();
    expect(within(screen.getByRole('link',{name:/Transport/})).queryByRole('progressbar')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Udział w wydatkach'}));
    expect(screen.getByText(/Udziały liczymy w dodatnich kwotach/)).toHaveTextContent('100,00');
    expect(within(screen.getByRole('link',{name:/Dom/})).getByRole('progressbar')).toHaveAttribute('aria-valuenow','100');
    expect(screen.getByText(/Zwroty przewyższają zakupy o/)).toHaveTextContent('50,00');
  });
});

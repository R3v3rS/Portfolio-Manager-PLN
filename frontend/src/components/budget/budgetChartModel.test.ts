import { describe, expect, it } from 'vitest';
import { budgetChartData } from './budgetChartModel';
import type { BudgetWorkspace } from '../../api_budget_workspace';
const workspace = (): BudgetWorkspace => ({ month: '2026-10', accounts: [], entries: [], bills: [], categories: [], totals: { balance: 1000, income: 0, planned: 0, spent: 0, remaining_in_plan: 0, to_plan: 1000 } });
describe('budget charts', () => {
  it('excludes fuel and its child limit only from daily pace, including refunds',()=>{
    const data=workspace();data.totals.planned=610;
    data.categories=[{id:1,name:'Transport',icon:'',manual_plan:610,planned_bills:0,planned:610,spent:300,remaining:310},{id:2,parent_id:1,name:'Paliwo',icon:'',manual_plan:300,planned_bills:0,planned:300,spent:220,remaining:80,daily_pace_included:false}];
    const entry={account_id:1,account_name:'PKO',date:'2026-10-08',merchant:null,has_receipt:false,loan_id:null,bill_id:null};
    data.entries=[{...entry,id:1,kind:'EXPENSE',amount:380,description:'Zakupy',lines:[{category_id:2,category_name:'Paliwo',label:'',amount:300},{category_id:1,category_name:'Transport',label:'',amount:80}]},{...entry,id:2,kind:'REFUND',refund_of:1,amount:80,description:'Zwrot paliwa',lines:[{category_id:2,category_name:'Paliwo',label:'',amount:80}]}];
    const chart=budgetChartData(data,'2026-10-08');
    expect(chart.dailyPace[7]).toMatchObject({spent:80,plan:80});
    expect(chart.pace[7].spent).toBe(300);
    expect(chart.pace.at(-1)?.plan).toBe(610);
    data.categories[0].daily_pace_included=false;
    expect(budgetChartData(data,'2026-10-08').dailyPace[7]).toMatchObject({spent:0,plan:0});
  });
  it('keeps an early fixed payment out of shopping and advances its planned amount',()=>{
    const data=workspace();data.totals.planned=1083;
    data.bills=[{id:1,title:'Czynsz',amount:850,planned_amount:773,paid_on:'2026-10-08',due_date:'2026-10-10',frequency:'MONTHLY',category_id:2,category_name:'Rachunki',account_id:1,account_name:'PKO',status:'PAID',entry_id:9}];
    data.categories=[{id:1,name:'Jedzenie',icon:'',manual_plan:310,planned_bills:0,planned:310,spent:80,remaining:230},{id:2,name:'Rachunki',icon:'',manual_plan:0,planned_bills:850,planned:850,spent:850,remaining:0}];
    const entry={account_id:1,account_name:'PKO',kind:'EXPENSE' as const,date:'2026-10-08',merchant:null,has_receipt:false,loan_id:null};
    data.entries=[{...entry,id:9,amount:850,description:'Czynsz',bill_id:1,lines:[{category_id:2,category_name:'Rachunki',label:'',amount:850}]},{...entry,id:10,amount:80,description:'Zakupy',bill_id:null,lines:[{category_id:1,category_name:'Jedzenie',label:'',amount:80}]}];
    const chart=budgetChartData(data,'2026-10-08');
    expect(chart.dailyPace[7]).toMatchObject({spent:80,plan:80});
    expect(chart.pace[7]).toMatchObject({spent:930,plan:853});
    expect(chart.pace.at(-1)?.plan).toBe(1083);
  });
  it('counts a shared parent limit and child bills once', () => {
    const data = workspace(); data.totals.planned = 1000;
    data.categories = [
      {id:1,name:'Transport',icon:'',planned:1000,spent:100,remaining:900,manual_plan:1000,planned_bills:200},
      {id:2,parent_id:1,name:'Paliwo',icon:'',planned:600,spent:100,remaining:500,manual_plan:600,planned_bills:0},
      {id:3,parent_id:1,name:'Bilety',icon:'',planned:200,spent:0,remaining:200,manual_plan:0,planned_bills:200},
    ];
    data.bills = [{id:1,title:'Bilet',amount:200,due_date:'2026-10-20',frequency:'ONCE',category_id:3,category_name:'',account_id:1,account_name:'',status:'UPCOMING',entry_id:null}];
    const result = budgetChartData(data,'2026-10-10');
    expect(result.remainingVariable).toBe(700);
    expect(result.closing).toBe(100);
    expect(result.forecast.at(-1)?.balance).toBe(100);
  });
  it('deducts only unpaid bills and avoids counting them twice in the category limit', () => {
    const data = workspace();
    data.categories = [{ id: 1, name: 'Rachunki', icon: '', planned: 500, spent: 200, remaining: 300, manual_plan: 500, planned_bills: 500 }];
    const bill = { title: 'Rachunek', frequency: 'ONCE' as const, category_id: 1, category_name: '', account_id: 1, account_name: '' };
    data.bills = [{ ...bill, id: 1, amount: 200, due_date: '2026-10-01', status: 'PAID', entry_id: 1 }, { ...bill, id: 2, amount: 300, due_date: '2026-10-20', status: 'UPCOMING', entry_id: null }];
    const result = budgetChartData(data, '2026-10-10');
    expect(result.unpaidTotal).toBe(300);
    expect(result.remainingVariable).toBe(0);
    expect(result.closing).toBe(700);
    expect(result.forecast.at(-1)?.balance).toBe(700);
  });
  it('places fixed bills on their due date and discretionary limits proportionally', () => {
    const data = workspace(); data.totals.planned = 610;
    data.bills = [{ id: 1, title: '', amount: 300, due_date: '2026-10-20', frequency: 'ONCE', category_id: 1, category_name: '', account_id: 1, account_name: '', status: 'UPCOMING', entry_id: null }];
    const result = budgetChartData(data, '2026-10-10');
    expect(result.pace[18].plan).toBe(190);
    expect(result.pace[19].plan).toBe(500);
    expect(result.pace[30].plan).toBe(610);
    expect(result.pace[10].spent).toBeNull();
  });
  it('adds simulation income only once and keeps historical months out of the forecast', () => {
    const data = workspace();
    expect(budgetChartData(data, '2026-10-10', 200).forecast.at(-1)?.balance).toBe(1200);
    expect(budgetChartData(data, '2026-11-10', 200).forecast).toEqual([]);
    expect(data.totals.balance).toBe(1000);
  });
});

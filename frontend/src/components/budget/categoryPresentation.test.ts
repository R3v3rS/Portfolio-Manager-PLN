import {describe,expect,it} from 'vitest';
import type {BudgetCategory} from '../../api_budget_workspace';
import {categoryPlanDescription,showCategory} from './categoryPresentation';
const category={id:1,name:'Zakupy spożywcze',manual_plan:0,planned:0,planned_bills:0,spent:40,remaining:-40,icon:'',plan_source:'NONE'} as BudgetCategory;
describe('Category meaning and visibility',()=>{
  it('shows a shared allowance instead of a false zero limit',()=>{
    const hint=categoryPlanDescription(category,{...category,name:'Jedzenie',planned:1200});
    expect(hint).toContain('wspólnego limitu');expect(hint).toMatch(/1\s?200,00/);
    expect(categoryPlanDescription({...category,planned_bills:250,planned:250})).toContain('Plan z rachunków');
    expect(categoryPlanDescription(category,{...category,name:'Rachunki',planned:1000,planned_bills:1000})).toContain('nowy zakup będzie dodatkowym kosztem');
  });
  it('keeps unused categories searchable and reversible without changing financial data',()=>{
    expect(showCategory({...category,has_activity:false},false,'')).toBe(false);
    expect(showCategory({...category,has_activity:false},true,'')).toBe(true);
    expect(showCategory({...category,has_activity:false},false,'Warzywa')).toBe(true);
    expect(showCategory({...category,has_activity:true},false,'')).toBe(true);
  });
});

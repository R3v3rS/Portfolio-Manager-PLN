import {describe,it,expect} from 'vitest';
import {shortfallPeriods} from './forecastPresentation';
describe('Forecast shortfall periods',()=>{
  it('distinguishes a temporary shortage from the positive final balance',()=>{
    const points=[{date:'2026-10-01',available:100},{date:'2026-10-02',available:-10},{date:'2026-10-03',available:-20},{date:'2026-10-04',available:100},{date:'2026-10-05',available:-30}];
    expect(shortfallPeriods(points,'2026-10-04')).toEqual([{start:'2026-10-02',end:'2026-10-03',open:false}]);
    expect(shortfallPeriods(points,'2026-10-05')).toEqual([{start:'2026-10-02',end:'2026-10-03',open:false},{start:'2026-10-05',end:'2026-10-05',open:true}]);
  });
});

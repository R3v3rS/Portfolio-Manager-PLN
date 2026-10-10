import { describe, expect, it } from 'vitest';
import type { RadarItem } from '../../types';
import { comparisonSeries, dataStatus, targetReached, upcomingEvents, emptyNotes } from './radarModel';

const now = new Date('2026-09-22T12:00:00');
const item = {ticker:'ABC',price:100,last_updated_at:'2026-09-22T11:00:00',notes:{...emptyNotes,target_price:110}} as RadarItem;
describe('radar data semantics', () => {
  it('distinguishes missing, stale and recent prices', () => {
    expect(dataStatus(item,now.getTime())).toBe('recent');
    expect(dataStatus({...item,price:null},now.getTime())).toBe('missing');
    expect(dataStatus({...item,last_updated_at:'2026-01-01'},now.getTime())).toBe('stale');
    expect(dataStatus({...item,last_updated_at:null},now.getTime())).toBe('stale');
  });
  it('never activates a price target using stale quotes', () => {
    expect(targetReached(item,now.getTime())).toBe(true);
    expect(targetReached({...item,last_updated_at:'2026-01-01'},now.getTime())).toBe(false);
    expect(targetReached({...item,notes:{...emptyNotes,target_price:110,target_direction:'above'}},now.getTime())).toBe(false);
  });
  it('excludes past market events and orders future dates', () => {
    expect(upcomingEvents([{...item,next_earnings:'2026-04-01',ex_dividend_date:'2026-09-24',notes:{...emptyNotes,review_date:'2026-09-23'}}],now).map(event => event.kind)).toEqual(['Twój przegląd','Odcięcie dywidendy']);
  });
  it('normalizes at the first common session and does not fill absent dates', () => {
    const series = comparisonSeries({A:[{date:'2026-09-18',close_price:50},{date:'2026-09-19',close_price:100},{date:'2026-09-21',close_price:110}],B:[{date:'2026-09-19',close_price:200},{date:'2026-09-20',close_price:202},{date:'2026-09-21',close_price:180}]},['A','B'],30,now);
    expect(series[0]).toEqual({date:'2026-09-19',A:0,B:0});
    expect(series).toHaveLength(2);
    expect(series[1].A).toBeCloseTo(10);
    expect(series[1].B).toBeCloseTo(-10);
    expect(comparisonSeries({A:[{date:'2026-09-19',close_price:100}]},['A','B'],30,now)).toEqual([]);
  });
});

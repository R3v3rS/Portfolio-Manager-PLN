import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import InvestmentRadar from './InvestmentRadar';
import { radarApi } from '../api_radar';
import type { RadarItem } from '../types';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../api_radar', () => ({ radarApi: { getAll: vi.fn(), history: vi.fn(), refresh: vi.fn(), saveNotes: vi.fn() } }));
vi.mock('recharts', () => ({
  ResponsiveContainer: () => <div aria-label="Wykres"/>, LineChart: () => null,
  Line: () => null, XAxis: () => null, YAxis: () => null, Tooltip: () => null,
  CartesianGrid: () => null, Legend: () => null,
}));
const items = ['AAA','BBB','CCC','DDD','EEE'].map((ticker, i) => ({
  ticker, company_name:`Company ${ticker}`, quantity:i === 0 ? 2 : 0, is_watched:i !== 0,
  price:i === 4 ? null : 100, last_updated_at:new Date().toISOString(), currency:'PLN',
  change_1d:1, change_1m:null, change_1y:null, instrument_type:'OTHER',
})) as RadarItem[];

beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear();
  vi.mocked(radarApi.getAll).mockResolvedValue(items);
  vi.mocked(radarApi.history).mockResolvedValue([]);
  vi.mocked(radarApi.refresh).mockResolvedValue({message:'OK',tickers:[]});
  vi.mocked(radarApi.saveNotes).mockResolvedValue(undefined);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('InvestmentRadar workflow', () => {
  it('filters by company and data status without losing selected instruments', async () => {
    render(<MemoryRouter><InvestmentRadar/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('checkbox',{name:'Porównaj AAA'}));
    fireEvent.change(screen.getByRole('searchbox'),{target:{value:'Company EEE'}});
    expect(screen.queryByRole('checkbox',{name:'Porównaj AAA'})).not.toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Usuń AAA z porównania'})).toBeInTheDocument();
    fireEvent.change(screen.getByRole('combobox',{name:'Status danych'}),{target:{value:'recent'}});
    expect(screen.getByText('Brak pasujących instrumentów')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Wyczyść filtry'}));
    expect(screen.getByRole('checkbox',{name:'Porównaj AAA'})).toBeChecked();
  });
  it('limits comparison to four instruments', async () => {
    render(<MemoryRouter><InvestmentRadar/></MemoryRouter>);
    await screen.findByRole('checkbox',{name:'Porównaj AAA'});
    for (const ticker of ['AAA','BBB','CCC','DDD']) fireEvent.click(screen.getByRole('checkbox',{name:`Porównaj ${ticker}`}));
    expect(screen.getByRole('checkbox',{name:'Porównaj EEE'})).toBeDisabled();
    fireEvent.click(screen.getByRole('button',{name:'Usuń AAA z porównania'}));
    expect(screen.getByRole('checkbox',{name:'Porównaj EEE'})).toBeEnabled();
  });
  it('retains cached instruments when refresh fails', async () => {
    vi.mocked(radarApi.refresh).mockRejectedValue(new Error('Dostawca niedostępny'));
    render(<MemoryRouter><InvestmentRadar/></MemoryRouter>);
    await screen.findByRole('checkbox',{name:'Porównaj AAA'});
    fireEvent.click(screen.getByRole('button',{name:'Odśwież dane'}));
    await screen.findByRole('alert');
    expect(screen.getByRole('checkbox',{name:'Porównaj AAA'})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Odśwież dane'})).toBeEnabled();
  });
  it('saves user notes and an explicit price condition', async () => {
    render(<MemoryRouter><InvestmentRadar/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button',{name:/AAA Company AAA/}));
    fireEvent.click(screen.getByRole('button',{name:'Moja obserwacja'}));
    fireEvent.change(screen.getByLabelText('Dlaczego obserwuję?'),{target:{value:'Sprawdzam wzrost przychodów'}});
    fireEvent.change(screen.getByLabelText('Poziom ceny'),{target:{value:'90'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz obserwację'}));
    await screen.findByText('Zapisano notatkę i poziom obserwacji.');
    expect(radarApi.saveNotes).toHaveBeenCalledWith('AAA',expect.objectContaining({thesis:'Sprawdzam wzrost przychodów',target_price:90,target_direction:'below'}));
  });
  it('stops automatic refresh when disabled and after unmount', async () => {
    const page = render(<MemoryRouter><InvestmentRadar/></MemoryRouter>);
    await screen.findByRole('checkbox',{name:'Porównaj AAA'});
    vi.useFakeTimers();
    await act(async () => { fireEvent.click(screen.getByRole('checkbox',{name:/Odświeżaj co 5 min/})); });
    expect(radarApi.refresh).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(300_000); });
    expect(radarApi.refresh).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole('checkbox',{name:/Odświeżaj co 5 min/}));
    await act(async () => { await vi.advanceTimersByTimeAsync(300_000); });
    expect(radarApi.refresh).toHaveBeenCalledTimes(2);
    page.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});

import {it,expect,vi} from 'vitest';
import {fireEvent,render,screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import StrategyComparison from './StrategyComparison';
import {reviewApi} from '../../api_investment_review';
vi.mock('../../api_investment_review',()=>({reviewApi:{strategies:vi.fn()}}));
it('separates frozen archives without adding their value to active assets',async()=>{
 vi.mocked(reviewApi.strategies).mockResolvedValue({parent_id:1,items:[{id:2,name:'Zamknięta',archived:true,frozen:true,started_at:'2025-01-01',closed_at:'2026-10-01',starting_capital:100,additional_capital:50,value:180,result:30,return_percent:20,valuation_status:'ok',xirr_percent:null}]});
 render(<MemoryRouter><StrategyComparison portfolioId={1}/></MemoryRouter>);
 expect(await screen.findByRole('link',{name:'Zamknięta'})).toBeInTheDocument();
 fireEvent.click(screen.getByRole('checkbox',{name:'Pokaż archiwum'}));
 expect(screen.queryByRole('link',{name:'Zamknięta'})).not.toBeInTheDocument();
 expect(screen.getByText(/Brak strategii w tym widoku/)).toBeInTheDocument();
});

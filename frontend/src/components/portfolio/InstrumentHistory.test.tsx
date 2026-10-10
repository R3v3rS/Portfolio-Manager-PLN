import {it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import InstrumentHistory from './InstrumentHistory';
import {reviewApi} from '../../api_investment_review';
vi.mock('../../api_investment_review',()=>({reviewApi:{instrument:vi.fn()},eventName:{ASSET_IN:'Przeniesienie do',SELL:'Sprzedaż'}}));
it('shows transfers and sales together with full instrument result',async()=>{
 vi.mocked(reviewApi.instrument).mockResolvedValue({ticker:'ABC',company_name:'Test',quantity:0,current_value:0,total_result:10,dividends:0,realized_profit:10,archived:false,price_basis:null,events:[{id:1,date:'2026-09-01',type:'ASSET_IN',quantity:1,price:130,total_value:130,remaining_quantity:1,realized_profit:0,strategy_name:'Nowa'},{id:2,date:'2026-10-01',type:'SELL',quantity:1,price:140,total_value:140,remaining_quantity:0,realized_profit:10,strategy_name:'Nowa'}]});
 render(<InstrumentHistory portfolioId={2} ticker="ABC" onClose={vi.fn()}/>);
 expect(await screen.findByRole('table')).toHaveTextContent('Przeniesienie do');
 expect(screen.getByRole('table')).toHaveTextContent('Sprzedaż');
 expect(screen.getByText('10,00 PLN')).toBeInTheDocument();
 expect(reviewApi.instrument).toHaveBeenCalledWith(2,'ABC');
});

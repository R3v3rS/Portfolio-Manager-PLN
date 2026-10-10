import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {beforeEach,expect,it,vi} from 'vitest';
import ManualPriceEditor from './ManualPriceEditor';
import {portfolioApi} from '../../api';
import type {Holding} from '../../types';

vi.mock('../../api',()=>({portfolioApi:{setManualPrice:vi.fn()}}));
const holding:Holding={id:1,portfolio_id:1,ticker:'ABC.WA',quantity:2,average_buy_price:100,total_cost:200,currency:'PLN',price_basis:'purchase',manual_price_version:0};
beforeEach(()=>{vi.resetAllMocks();vi.mocked(portfolioApi.setManualPrice).mockResolvedValue({});});
it('saves a dated unit reference with its version, then refreshes the portfolio',async()=>{
  const saved=vi.fn(async()=>{}),close=vi.fn();
  render(<MemoryRouter><ManualPriceEditor holding={holding} onClose={close} onSaved={saved}/></MemoryRouter>);
  fireEvent.change(screen.getByLabelText('Cena jednej akcji (PLN)'),{target:{value:'130.5'}});
  fireEvent.change(screen.getByLabelText('Data ceny'),{target:{value:'2026-10-01'}});
  fireEvent.click(screen.getByRole('button',{name:'Zapisz cenę'}));
  await waitFor(()=>expect(saved).toHaveBeenCalledOnce());
  expect(portfolioApi.setManualPrice).toHaveBeenCalledWith('ABC.WA',{price:130.5,date:'2026-10-01',version:0,clear:false});
  expect(close).toHaveBeenCalledOnce();
});
it('can return to automatic prices without editing purchases',async()=>{
  render(<MemoryRouter><ManualPriceEditor holding={{...holding,price_basis:'manual',current_price:130,manual_price_version:4,price_last_updated_at:'2026-10-01'}} onClose={()=>{}} onSaved={async()=>{}}/></MemoryRouter>);
  fireEvent.click(screen.getByRole('button',{name:'Wróć do notowań automatycznych'}));
  await waitFor(()=>expect(portfolioApi.setManualPrice).toHaveBeenCalledWith('ABC.WA',expect.objectContaining({version:4,clear:true})));
});

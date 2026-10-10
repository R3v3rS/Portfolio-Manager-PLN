import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {beforeEach,expect,it,vi} from 'vitest';
import AssetTransfer from './AssetTransfer';
import {portfolioApi} from '../../api';
vi.mock('../../api',()=>({portfolioApi:{assetTransferPositions:vi.fn(),transferAsset:vi.fn()}}));
beforeEach(()=>{vi.resetAllMocks();vi.mocked(portfolioApi.assetTransferPositions).mockResolvedValue({positions:[{id:1,portfolio_id:1,ticker:'ABC',quantity:2,average_buy_price:100,total_cost:200,source_id:null,source_name:'Część główna',current_price:130,fx_rate_used:1}],scopes:[{id:null,name:'Część główna'},{id:9,name:'Nowe'}]});vi.mocked(portfolioApi.transferAsset).mockResolvedValue({});});
it('moves a partial position with an explicit entry valuation and refreshes after booking',async()=>{
  const saved=vi.fn(async()=>{});render(<AssetTransfer parentId={1} onSaved={saved}/>);
  fireEvent.click(screen.getByRole('button',{name:'Przenieś akcje do podkonta'}));
  await waitFor(()=>expect(portfolioApi.assetTransferPositions).toHaveBeenCalledWith(1));
  await screen.findByRole('option',{name:'ABC · Część główna · 2 szt.'});
  fireEvent.change(screen.getByLabelText('Pozycja i konto źródłowe'),{target:{value:'0'}});
  fireEvent.change(screen.getByLabelText('Konto docelowe'),{target:{value:'9'}});
  fireEvent.change(screen.getByLabelText('Liczba jednostek'),{target:{value:'1'}});
  fireEvent.change(screen.getByLabelText('Wartość jednej jednostki na start (PLN)'),{target:{value:'130'}});
  fireEvent.click(screen.getByRole('button',{name:'Przenieś i rozpocznij historię'}));
  await waitFor(()=>expect(saved).toHaveBeenCalledOnce());
  expect(portfolioApi.transferAsset).toHaveBeenCalledWith({portfolio_id:1,source_id:null,target_id:9,ticker:'ABC',quantity:1,price_pln:130,expected_quantity:2});
});

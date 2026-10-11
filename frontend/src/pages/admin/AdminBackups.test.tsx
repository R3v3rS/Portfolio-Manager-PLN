import {beforeEach,describe,it,expect,vi} from 'vitest';
import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import AdminBackups from './AdminBackups';
import {backupsApi} from '../../api_backups';
vi.mock('../../api_backups',()=>({backupsApi:{get:vi.fn(),create:vi.fn(),restore:vi.fn()}}));
describe('Database backups',()=>{
 beforeEach(()=>{vi.clearAllMocks();vi.mocked(backupsApi.get).mockResolvedValue({items:[{name:'manual-test.db',created_at:'2026-10-10T10:00:00',size:1024,kind:'manual'}],daily_retention:14,update_retention:10});});
 it('requires explicit typed confirmation before restoring',async()=>{
  vi.mocked(backupsApi.restore).mockResolvedValue({restored:'manual-test.db',rescue_copy:'before-restore-test.db'});
  render(<AdminBackups/>);fireEvent.click(await screen.findByRole('button',{name:'Przywróć'}));
  expect(screen.getByRole('button',{name:'Przywróć całą bazę'})).toBeDisabled();
  expect(backupsApi.restore).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Potwierdzenie przywrócenia'),{target:{value:'PRZYWRÓĆ'}});
  fireEvent.click(screen.getByRole('button',{name:'Przywróć całą bazę'}));
  await waitFor(()=>expect(backupsApi.restore).toHaveBeenCalledWith('manual-test.db','PRZYWRÓĆ'));
  expect(await screen.findByText(/before-restore-test.db/)).toBeInTheDocument();
 });
});

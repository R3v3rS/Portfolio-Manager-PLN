import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BudgetImports from './BudgetImports';
import { budgetImportsApi, type BankImportSession, type BudgetImportsWorkspace, type ExpenseCandidate, type ReceiptDraft } from '../api_budget_imports';

vi.mock('../api_budget_imports', () => ({ budgetImportsApi: {
  get:vi.fn(), preview:vi.fn(), stage:vi.fn(), session:vi.fn(), updateRow:vi.fn(), refresh:vi.fn(), commit:vi.fn(),
  saveRule:vi.fn(), updateRule:vi.fn(), saveTransferRule:vi.fn(), updateTransferRule:vi.fn(), categorize:vi.fn(), applyRules:vi.fn(), matches:vi.fn(), uploadReceipt:vi.fn(),
  receipt:vi.fn(), receiptFile:(id:number)=>`/receipt/${id}`, parseReceipt:vi.fn(), commitReceipt:vi.fn(), deleteReceipt:vi.fn(), recognizeReceipt:vi.fn(),
} }));
const candidate = (): ExpenseCandidate => ({ id:9,account_id:2,account_name:'Konto osobiste',date:'2026-10-02',amount:146.8,
  description:'Zakupy LIDL',merchant:'LIDL',version:3,has_receipt:false,classification_status:'UNASSIGNED',merchant_match:true,lines:[] });
const workspace = (): BudgetImportsWorkspace => ({ accounts:[{id:2,name:'Konto osobiste',balance:10000,verified_on:null},{id:4,name:'Oszczędności',balance:500,verified_on:null}],
  categories:[{id:1,name:'Jedzenie'},{id:3,name:'Media'}], rules:[], pending:[{...candidate()}], pending_count:1,sessions:[],receipts:[],ocr:{available:true,local:true},selected_entry:null });
const session = (): BankImportSession => ({ id:5,account_id:2,account_name:'Konto osobiste',filename:'wyciag.csv',balance_mode:'HISTORY',status:'PENDING',version:1,
  opening_balance:10000,expected_balance:10000,closing_balance:10000,cash_delta:0,result:null,
  rows:[{id:8,row_number:1,action:'NEW',kind:'EXPENSE',bank_kind:'EXPENSE',date:'2026-10-02',amount:300,description:'Faktura energia',merchant:'ENEA',
    category_id:3,rule_name:'Prąd',entry_id:null,transfer_id:null,target_account_id:null,errors:[],warnings:[],candidates:[],source_exists:false,transfer_candidates:[]}] });
const receipt = (): ReceiptDraft => ({ id:6,version:2,status:'PENDING',account_id:2,entry_id:null,filename:'paragon.png',is_pdf:false,
  raw_text:'LIDL\n2026-10-02\nSUMA PLN 146,80',data:{merchant:'LIDL',date:'2026-10-02',amount:146.8,category_id:null,
    lines:[{label:'Jedzenie',amount:112.4,category_id:1},{label:'Chemia',amount:34.4,category_id:3}]},warnings:[],candidates:[candidate()] });
const show=(path='/budget/imports')=>render(<MemoryRouter initialEntries={[path]}><BudgetImports/></MemoryRouter>);
const ready=()=>screen.findByRole('heading',{name:'Zakupy do przypisania'});
const uploadPhoto=async()=>{fireEvent.change(screen.getByLabelText('Zdjęcie lub PDF paragonu'),{target:{files:[new File(['photo'],'paragon.png',{type:'image/png'})]}});await screen.findByLabelText('Kwota zakupu (PLN)');};

beforeEach(()=>{
  vi.resetAllMocks();vi.mocked(budgetImportsApi.get).mockResolvedValue(workspace());
  vi.mocked(budgetImportsApi.categorize).mockResolvedValue({updated:1});vi.mocked(budgetImportsApi.applyRules).mockResolvedValue({updated:1,unmatched:0});
  vi.mocked(budgetImportsApi.saveRule).mockResolvedValue({id:7});vi.mocked(budgetImportsApi.updateRule).mockResolvedValue({id:7});
  vi.mocked(budgetImportsApi.preview).mockResolvedValue({columns:['Data','Opis','Kwota'],sample:[['02.10.2026','ENEA','-300,00']],count:1,header_index:0,encoding:'utf-8-sig',delimiter:';',remembered:false,
    mapping:{date:'0',description:'1',amount:'2',merchant:'',currency:'',reference:'',debit:'',credit:''}});
  vi.mocked(budgetImportsApi.stage).mockResolvedValue({id:5});vi.mocked(budgetImportsApi.session).mockResolvedValue(session());
  vi.mocked(budgetImportsApi.commit).mockResolvedValue({created:1,linked:0,transfers:0,skipped:0,balance:10000,balance_mode:'HISTORY'});
  vi.mocked(budgetImportsApi.uploadReceipt).mockResolvedValue({id:6});vi.mocked(budgetImportsApi.receipt).mockResolvedValue(receipt());
  vi.mocked(budgetImportsApi.commitReceipt).mockResolvedValue({entry_id:9,linked:true});vi.mocked(budgetImportsApi.matches).mockResolvedValue([candidate()]);
});
afterEach(()=>{cleanup();vi.restoreAllMocks();document.body.style.overflow='';});

describe('Budget imports',()=>{
  it('replaces the draft with a fresh readout only after confirming',async()=>{
    vi.spyOn(window,'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    vi.mocked(budgetImportsApi.recognizeReceipt).mockResolvedValue({id:6});
    const improved=receipt();improved.version=3;improved.data.amount=41.44;improved.data.merchant='Dino';improved.data.lines=[];improved.candidates=[];
    vi.mocked(budgetImportsApi.receipt).mockResolvedValueOnce(receipt()).mockResolvedValue(improved);
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    fireEvent.click(screen.getByRole('button',{name:'Odczytaj ponownie'}));expect(budgetImportsApi.recognizeReceipt).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Odczytaj ponownie'}));
    await waitFor(()=>expect(screen.getByLabelText('Kwota zakupu (PLN)')).toHaveValue(41.44));
    expect(budgetImportsApi.recognizeReceipt).toHaveBeenCalledWith(6,2);
    expect(screen.getByLabelText('Sklep / odbiorca')).toHaveValue('Dino');
    expect(budgetImportsApi.commitReceipt).not.toHaveBeenCalled();
  });
  it('retains manual edits when repeat recognition fails',async()=>{
    vi.spyOn(window,'confirm').mockReturnValue(true);
    vi.mocked(budgetImportsApi.recognizeReceipt).mockRejectedValue(new Error('Nie udało się odczytać'));
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    fireEvent.change(screen.getByLabelText('Sklep / odbiorca'),{target:{value:'Ręczna poprawka'}});
    fireEvent.click(screen.getByRole('button',{name:'Odczytaj ponownie'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się odczytać');
    expect(screen.getByLabelText('Sklep / odbiorca')).toHaveValue('Ręczna poprawka');
  });
  it('cancels receipt deletion without calling the API',async()=>{
    vi.spyOn(window,'confirm').mockReturnValue(false);
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    fireEvent.click(screen.getByRole('button',{name:'Usuń paragon'}));
    expect(budgetImportsApi.deleteReceipt).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Kwota zakupu (PLN)')).toBeInTheDocument();
  });
  it('deletes a receipt with confirmation and removes it even when refreshing fails',async()=>{
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(true);
    const w=workspace();w.receipts=[{id:6,filename:'paragon.png',status:'PENDING',entry_id:null,created_at:'2026-10-03'}];
    vi.mocked(budgetImportsApi.get).mockResolvedValueOnce(w).mockRejectedValue(new Error('Brak połączenia'));
    vi.mocked(budgetImportsApi.deleteReceipt).mockResolvedValue({deleted:6});
    show('/budget/imports?tab=receipt');fireEvent.click(await screen.findByRole('button',{name:/paragon.png/}));
    fireEvent.click(await screen.findByRole('button',{name:'Usuń paragon'}));
    await waitFor(()=>expect(budgetImportsApi.deleteReceipt).toHaveBeenCalledWith(6,2));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Zapisany wydatek, jego kategorie i saldo konta pozostaną bez zmian'));
    await screen.findByLabelText('Zdjęcie lub PDF paragonu');
    expect(screen.queryByRole('button',{name:/paragon.png/})).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Paragon usunięty');
  });
  it('retains the receipt and shows an error if deleting fails',async()=>{
    vi.spyOn(window,'confirm').mockReturnValue(true);
    vi.mocked(budgetImportsApi.deleteReceipt).mockRejectedValue(new Error('Paragon zmienił się'));
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    fireEvent.click(screen.getByRole('button',{name:'Usuń paragon'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Paragon zmienił się');
    expect(screen.getByLabelText('Kwota zakupu (PLN)')).toBeInTheDocument();
  });
  it('can delete a committed receipt immediately using the updated version',async()=>{
    vi.spyOn(window,'confirm').mockReturnValue(true);
    vi.mocked(budgetImportsApi.deleteReceipt).mockResolvedValue({deleted:6});
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    fireEvent.click(screen.getByRole('button',{name:'Połącz paragon i zapisz podział'}));
    await screen.findByRole('heading',{name:'Paragon zapisany'});
    fireEvent.click(screen.getByRole('button',{name:'Usuń paragon'}));
    await waitFor(()=>expect(budgetImportsApi.deleteReceipt).toHaveBeenCalledWith(6,3));
  });
  it('saves a purpose rule with the two own accounts and the reserve',async()=>{
    vi.mocked(budgetImportsApi.get).mockResolvedValue({...workspace(),reserves:[{id:7,name:'OC auta',version:1}],transfer_rules:[]});
    vi.mocked(budgetImportsApi.saveTransferRule).mockResolvedValue({id:3});
    show();await ready();fireEvent.click(screen.getByRole('tab',{name:'Reguły kategorii i rezerw'}));
    fireEvent.click(screen.getByRole('button',{name:'Reguła przelewu na rezerwę'}));
    fireEvent.change(screen.getByLabelText('Cel w opisie przelewu'),{target:{value:'rezerwa OC auta'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz regułę przelewu'}));
    await waitFor(()=>expect(budgetImportsApi.saveTransferRule).toHaveBeenCalledWith({pattern:'rezerwa OC auta',source_account_id:2,
      target_account_id:4,reserve_id:7,active:true},expect.any(String)));
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('shows funding amount in CSV review and permits choosing a reserve',async()=>{
    vi.mocked(budgetImportsApi.get).mockResolvedValue({...workspace(),reserves:[{id:7,name:'OC auta',version:1}]});
    const draft=session();draft.rows[0]={...draft.rows[0],kind:'TRANSFER',reserve_id:7,target_account_id:4};
    vi.mocked(budgetImportsApi.session).mockResolvedValue(draft);
    show();await ready();fireEvent.click(screen.getByRole('tab',{name:'Import CSV'}));
    fireEvent.change(screen.getByLabelText('Bankowy plik CSV'),{target:{files:[new File(['csv'],'bank.csv')]}});
    await screen.findByRole('button',{name:'Przygotuj do sprawdzenia'});
    fireEvent.click(screen.getByRole('button',{name:'Przygotuj do sprawdzenia'}));
    await screen.findByLabelText('Rezerwa operacji 1');
    expect(screen.getByText(/Odłożenia na rezerwy: 300,00/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Rezerwa operacji 1'),{target:{value:''}});
    await waitFor(()=>expect(budgetImportsApi.updateRow).toHaveBeenCalledWith(5,8,{version:1,reserve_id:null}));
  });
  it('assigns a whole purchase without requiring a receipt or moving money',async()=>{
    show();await ready();fireEvent.change(screen.getByLabelText('Kategoria wydatku: Zakupy LIDL'),{target:{value:'1'}});
    fireEvent.click(screen.getByRole('button',{name:'Przypisz kategorię: Zakupy LIDL'}));
    await waitFor(()=>expect(budgetImportsApi.categorize).toHaveBeenCalledWith([9],{'9':3},1));
    expect((await screen.findAllByRole('status'))[0]).toHaveTextContent('Salda kont pozostają bez zmian');
    fireEvent.click(screen.getByRole('button',{name:'Tak, utwórz regułę'}));
    const dialog=within(screen.getByRole('dialog',{name:'Zapamiętaj kategorię kolejnych płatności'}));
    expect(dialog.getByLabelText('Dokładna nazwa odbiorcy')).toHaveValue('LIDL');
    fireEvent.click(dialog.getByRole('button',{name:'Zapisz regułę'}));
    await waitFor(()=>expect(budgetImportsApi.saveRule).toHaveBeenCalledWith(expect.objectContaining({pattern:'LIDL',category_id:1,account_id:2,match_field:'MERCHANT',match_type:'EQUALS'}),expect.any(String)));
    expect(budgetImportsApi.commitReceipt).not.toHaveBeenCalled();expect(budgetImportsApi.commit).not.toHaveBeenCalled();
  });
  it('uses current versions for batch categorization and links manual splitting',async()=>{
    show();await ready();fireEvent.click(screen.getByRole('checkbox',{name:'Wybierz wydatek: Zakupy LIDL'}));
    fireEvent.change(screen.getByLabelText('Kategoria zaznaczonych'),{target:{value:'1'}});
    fireEvent.click(screen.getByRole('button',{name:'Przypisz zaznaczone (1)'}));
    await waitFor(()=>expect(budgetImportsApi.categorize).toHaveBeenCalledWith([9],{'9':3},1));
    expect(screen.getByRole('link',{name:'Podziel ręcznie: Zakupy LIDL'})).toHaveAttribute('href','/budget?view=entries&month=2026-10&edit_entry=9');
  });
  it('creates an ENEA rule with a new category and optional account scope',async()=>{
    show();await ready();fireEvent.click(screen.getByRole('button',{name:'Dodaj regułę'}));
    const dialog=screen.getByRole('dialog');fireEvent.change(within(dialog).getByLabelText('Tekst do dopasowania'),{target:{value:'ENEA'}});
    fireEvent.change(within(dialog).getByLabelText('Kategoria docelowa'),{target:{value:'NEW'}});
    fireEvent.change(within(dialog).getByLabelText('Nazwa nowej kategorii'),{target:{value:'Prąd / media'}});
    fireEvent.change(within(dialog).getByLabelText('Obowiązuje dla konta'),{target:{value:'2'}});
    fireEvent.click(within(dialog).getByRole('button',{name:'Zapisz regułę'}));
    await waitFor(()=>expect(budgetImportsApi.saveRule).toHaveBeenCalledWith(expect.objectContaining({pattern:'ENEA',new_category:'Prąd / media',category_id:null,account_id:2,match_field:'ANY',match_type:'CONTAINS',priority:100,active:true}),expect.any(String)));
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
  it('retains the same request identity after an uncertain rule save and closes after success',async()=>{
    vi.mocked(budgetImportsApi.saveRule).mockRejectedValueOnce(new Error('Brak odpowiedzi'));
    show();await ready();fireEvent.click(screen.getByRole('button',{name:'Dodaj regułę'}));
    fireEvent.change(screen.getByLabelText('Tekst do dopasowania'),{target:{value:'LIDL'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz regułę'}));await screen.findByRole('alert');
    const token=vi.mocked(budgetImportsApi.saveRule).mock.calls[0][1];
    fireEvent.click(screen.getByRole('button',{name:'Zapisz regułę'}));
    await waitFor(()=>expect(budgetImportsApi.saveRule).toHaveBeenLastCalledWith(expect.any(Object),token));
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
  it('applies permanent rules to existing unassigned purchases explicitly',async()=>{
    const w=workspace();w.rules=[{id:7,version:1,name:'LIDL',pattern:'LIDL',match_field:'ANY',match_type:'CONTAINS',category_id:1,category_name:'Jedzenie',account_id:null,account_name:null,priority:100,active:true}];
    vi.mocked(budgetImportsApi.get).mockResolvedValue(w);show();await ready();
    fireEvent.click(screen.getByRole('button',{name:'Zastosuj reguły'}));
    await waitFor(()=>expect(budgetImportsApi.applyRules).toHaveBeenCalledWith([9],{'9':3}));
    expect((await screen.findAllByRole('status'))[0]).toHaveTextContent('Reguły przypisały 1 wydatków');
  });
  it('prepares CSV in history mode with column mapping and rule proposals before committing',async()=>{
    vi.mocked(budgetImportsApi.commit).mockResolvedValue({created:1,linked:0,transfers:0,skipped:0,balance:10000,balance_mode:'HISTORY',bill_matches:[{bill_id:8,title:'ENEA',month:'2026-10',entry_ids:[9]}]});
    show();await ready();fireEvent.click(screen.getByRole('tab',{name:'Import CSV'}));
    const file=new File(['csv'],'wyciag.csv',{type:'text/csv'});fireEvent.change(screen.getByLabelText('Bankowy plik CSV'),{target:{files:[file]}});
    await screen.findByRole('button',{name:'Przygotuj do sprawdzenia'});fireEvent.click(screen.getByRole('button',{name:'Przygotuj do sprawdzenia'}));
    await screen.findByText('Reguła: Prąd');expect(budgetImportsApi.stage).toHaveBeenCalledWith(file,expect.objectContaining({account_id:2,balance_mode:'HISTORY',header_index:0,mapping:expect.objectContaining({amount:'2'})}),expect.any(String));
    expect(budgetImportsApi.commit).not.toHaveBeenCalled();expect(screen.getByLabelText('Kategoria operacji 1')).toHaveValue('3');
    fireEvent.click(screen.getByRole('button',{name:'Zatwierdź import'}));
    await screen.findByRole('heading',{name:'Import zapisany'});expect(budgetImportsApi.commit).toHaveBeenCalledWith(5,1,expect.any(String));
    expect(screen.getByRole('link',{name:'Powiąż: ENEA · 2026-10'})).toHaveAttribute('href','/budget?view=bills&month=2026-10&bill=8');
    expect(screen.queryByRole('button',{name:'Zatwierdź import'})).not.toBeInTheDocument();
  });
  it('does not expose a second CSV commit if refreshing the workspace fails after saving',async()=>{
    const w=workspace();w.sessions=[{id:5,filename:'wyciag.csv',created_at:'2026-10-03',status:'PENDING',version:1,balance_mode:'HISTORY',account_name:'Konto osobiste',row_count:1}];
    vi.mocked(budgetImportsApi.get).mockResolvedValueOnce(w).mockRejectedValue(new Error('Brak połączenia'));
    show();await ready();fireEvent.click(screen.getByRole('tab',{name:'Historia importów'}));
    fireEvent.click(screen.getByRole('button',{name:/wyciag.csv/}));await screen.findByRole('button',{name:'Zatwierdź import'});
    fireEvent.click(screen.getByRole('button',{name:'Zatwierdź import'}));await screen.findByRole('heading',{name:'Import zapisany'});
    expect(await screen.findByRole('alert')).toHaveTextContent('Pokazujemy ostatnio odczytane dane');
    expect(screen.queryByRole('button',{name:'Zatwierdź import'})).not.toBeInTheDocument();
  });
  it('blocks malformed CSV rows until they are skipped',async()=>{
    const w=workspace();w.sessions=[{id:5,filename:'wyciag.csv',created_at:'2026-10-03',status:'PENDING',version:1,balance_mode:'HISTORY',account_name:'Konto osobiste',row_count:1}];
    const s=session();s.rows[0].errors=['Kwota nie jest w PLN'];vi.mocked(budgetImportsApi.get).mockResolvedValue(w);vi.mocked(budgetImportsApi.session).mockResolvedValue(s);
    show();await ready();fireEvent.click(screen.getByRole('tab',{name:'Historia importów'}));fireEvent.click(screen.getByRole('button',{name:/wyciag.csv/}));
    expect(await screen.findByRole('button',{name:'Zatwierdź import'})).toBeDisabled();expect(budgetImportsApi.commit).not.toHaveBeenCalled();
  });
  it('links a receipt to the existing bank purchase and saves a split without another expense',async()=>{
    const w=workspace();w.selected_entry=candidate();vi.mocked(budgetImportsApi.get).mockResolvedValue(w);
    show('/budget/imports?tab=receipt&entry_id=9');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    expect(budgetImportsApi.get).toHaveBeenCalledWith(9,200);expect(screen.getByLabelText('Do którego wpisu dołączyć paragon')).toHaveValue('9');
    fireEvent.click(screen.getByRole('button',{name:'Połącz paragon i zapisz podział'}));
    await waitFor(()=>expect(budgetImportsApi.commitReceipt).toHaveBeenCalledWith(6,expect.objectContaining({action:'MATCH',entry_id:9,entry_version:3,account_id:2,amount:146.8,classification_mode:'SPLIT',lines:[{label:'Jedzenie',amount:112.4,category_id:1},{label:'Chemia',amount:34.4,category_id:3}]}),2,expect.any(String)));
    await screen.findByRole('heading',{name:'Paragon zapisany'});expect(budgetImportsApi.commit).not.toHaveBeenCalled();
  });
  it('blocks mismatched product sums and wrong receipt totals',async()=>{
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    fireEvent.change(screen.getByLabelText('Kwota pozycji 1'),{target:{value:'100'}});
    expect(screen.getByRole('button',{name:'Połącz paragon i zapisz podział'})).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Jak przypisać wydatek'),{target:{value:'KEEP'}});
    fireEvent.change(screen.getByLabelText('Kwota zakupu (PLN)'),{target:{value:'200'}});
    expect(screen.getByRole('button',{name:'Połącz paragon i zapisz podział'})).toBeDisabled();expect(budgetImportsApi.commitReceipt).not.toHaveBeenCalled();
  });
  it('requires real categories for products when the bank purchase is still unassigned',async()=>{
    const r=receipt();r.candidates[0].lines=[{category_id:99,category_name:'Nieprzypisane',amount:146.8,label:''}];
    r.data.lines=r.data.lines.map(l=>({...l,category_id:null}));vi.mocked(budgetImportsApi.receipt).mockResolvedValue(r);
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    expect(screen.getByLabelText('Kategoria pozycji 1')).toHaveValue('');
    expect(screen.getByRole('button',{name:'Połącz paragon i zapisz podział'})).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Wspólna kategoria pozycji'),{target:{value:'1'}});
    fireEvent.click(screen.getByRole('button',{name:'Przypisz tę kategorię wszystkim pozycjom'}));
    expect(screen.getByRole('button',{name:'Połącz paragon i zapisz podział'})).toBeEnabled();
  });
  it('requires explicit confirmation when creating a new receipt expense despite a similar bank purchase',async()=>{
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    fireEvent.change(screen.getByLabelText('Do którego wpisu dołączyć paragon'),{target:{value:''}});
    expect(screen.getByRole('button',{name:'Zapisz wydatek z paragonem'})).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox',{name:/Potwierdzam, że to odrębny zakup/}));
    fireEvent.click(screen.getByRole('button',{name:'Zapisz wydatek z paragonem'}));
    await waitFor(()=>expect(budgetImportsApi.commitReceipt).toHaveBeenCalledWith(6,expect.objectContaining({action:'NEW',confirm_separate:true,balance_mode:'HISTORY'}),2,expect.any(String)));
  });
  it('keeps manual completion available when OCR could not read a photo',async()=>{
    const r=receipt();r.data={merchant:'',date:'',amount:null,category_id:null,lines:[]};r.candidates=[];r.warnings=['Nie udało się odczytać pliku lokalnie'];
    vi.mocked(budgetImportsApi.receipt).mockResolvedValue(r);show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    expect(screen.getByText('Nie udało się odczytać pliku lokalnie')).toBeInTheDocument();expect(screen.getByLabelText('Kwota zakupu (PLN)')).toBeEnabled();
    expect(screen.getByLabelText('Jak przypisać wydatek')).toHaveValue('KEEP');
    expect(screen.getByLabelText('Data zakupu')).toHaveValue('');
  });
  it('does not select a split automatically when recognized products do not balance',async()=>{
    const r=receipt();r.data.lines=[{label:'PINO HIL',amount:.51,category_id:null}];
    vi.mocked(budgetImportsApi.receipt).mockResolvedValue(r);
    show('/budget/imports?tab=receipt');await screen.findByLabelText('Zdjęcie lub PDF paragonu');await uploadPhoto();
    expect(screen.getByLabelText('Jak przypisać wydatek')).toHaveValue('KEEP');
  });
  it('shows a failed initial read rather than empty figures',async()=>{
    vi.mocked(budgetImportsApi.get).mockRejectedValue(new Error('Nie można wczytać danych'));show();
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie można wczytać danych');expect(screen.queryByLabelText('Stan uzupełniania budżetu')).not.toBeInTheDocument();
  });
});

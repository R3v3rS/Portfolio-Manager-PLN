"""Atomic accounting of bond purchases, actual payouts and cancellations."""
import csv
import hashlib
import io
import json
import math
from datetime import date
from database import get_db
from api.exceptions import ValidationError, NotFoundError
from bond_model import KINDS, estimate, money, shift

BOND_COLUMNS='id,portfolio_id,name,principal,interest_rate,CAST(purchase_date AS TEXT) AS purchase_date,kind,quantity,nominal,purchase_price,maturity_date,tax_rate,redemption_fee,fee_policy,payout_account_id,forecast_enabled,acquisition,status,version,notes'

def day(value, label='Data', future=False):
    try:
        parsed=date.fromisoformat(str(value))
        if parsed.isoformat()!=value or not 2000<=parsed.year<=2100 or (not future and parsed>date.today()):raise ValueError
        return parsed
    except (ValueError,TypeError):raise ValidationError(f'{label}: podaj poprawną datę'+('.' if future else ', nie późniejszą niż dziś.')) from None

def number(value,label,low=0,high=999999999.99,integer=False):
    try:
        if isinstance(value,bool):raise ValueError
        result=float(value)
        if not math.isfinite(result) or not low<=result<=high or (integer and result!=int(result)):raise ValueError
        return int(result) if integer else result
    except (ValueError,TypeError,OverflowError):raise ValidationError(f'{label}: nieprawidłowa wartość.') from None

def amount(value,label,positive=False):
    result=number(value,label,.01 if positive else 0)
    if money(result)!=result:raise ValidationError(f'{label}: najwyżej dwa miejsca po przecinku.')
    return result

def validate(data):
    kind=data.get('kind','CUSTOM')
    if kind not in KINDS:raise ValidationError('Wybierz rodzaj obligacji.')
    name=data.get('name','')
    if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValidationError('Podaj nazwę lub serię (do 100 znaków).')
    purchase=day(data.get('purchase_date'),'Data zakupu')
    qty=number(data.get('quantity',1),'Liczba sztuk',1,1000000,True)
    nominal=amount(data.get('nominal',100),'Nominał',True)
    if kind!='CUSTOM' and nominal!=100:raise ValidationError('Nominał jednej obligacji detalicznej wynosi 100 zł.')
    price=amount(data.get('purchase_price',nominal),'Cena zakupu jednej sztuki',True)
    principal=money(qty*price)
    if principal>999999999.99:raise ValidationError('Zbyt duża wartość zakupu.')
    end=shift(purchase,KINDS[kind]['months']) if KINDS[kind]['months'] else day(data.get('maturity_date'),'Termin wykupu',True)
    if end<=purchase:raise ValidationError('Wykup musi być późniejszy niż zakup.')
    rate=number(data.get('interest_rate'),'Oprocentowanie',0,100)
    tax=number(data.get('tax_rate',19),'Stawka podatku',0,100)
    fee=None if data.get('redemption_fee') in (None,'') else amount(data['redemption_fee'],'Opłata wykupu za sztukę')
    fee_policy=data.get('fee_policy','CAP_INTEREST')
    if fee_policy not in ('CAP_INTEREST','FIRST_PERIOD','FULL'):raise ValidationError('Wybierz zasadę potrącenia opłaty.')
    notes=data.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000:raise ValidationError('Notatka: do 2000 znaków.')
    account=data.get('payout_account_id')
    account=number(account,'Konto wypłaty',1,999999999,True) if account not in (None,'') else None
    forecast=data.get('forecast_enabled',False)
    if not isinstance(forecast,bool):raise ValidationError('Nieprawidłowy wybór prognozy.')
    if forecast and not account:raise ValidationError('Wybierz konto planowanych wypłat.')
    return dict(name=name.strip(),kind=kind,quantity=qty,nominal=nominal,purchase_price=price,
        principal=principal,purchase_date=purchase.isoformat(),maturity_date=end.isoformat(),interest_rate=rate,
        tax_rate=tax,redemption_fee=fee,fee_policy=fee_policy,notes=notes,payout_account_id=account,forecast_enabled=int(forecast))

def portfolio(db,pid):
    p=db.execute('SELECT * FROM portfolios WHERE id=?',(pid,)).fetchone()
    if not p:raise NotFoundError('Nie znaleziono portfela.')
    if p['account_type']!='BONDS' or p['is_archived'] or p['parent_portfolio_id']:raise ValidationError('Operacja wymaga aktywnego portfela obligacji.')
    return p

def account_check(db,account_id):
    if account_id is None:return
    a=db.execute('SELECT * FROM budget_accounts WHERE id=?',(account_id,)).fetchone()
    if not a or (a['currency'] or 'PLN').upper()!='PLN':raise ValidationError('Wybierz istniejące konto budżetowe w PLN.')

def tx(db,pid,bid,kind,value,when,qty=1,profit=0):
    return db.execute('''INSERT INTO transactions(portfolio_id,ticker,type,quantity,price,total_value,date,realized_profit)
        VALUES(?,?,?,?,?,?,?,?)''',(pid,f'BOND:{bid}',kind,qty,money(value/qty),value,when,profit)).lastrowid

def invalidate(db,pid):
    db.execute('DELETE FROM portfolio_history_cache WHERE portfolio_id=?',(pid,))
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='analytics_cache'").fetchone():db.execute('DELETE FROM analytics_cache WHERE portfolio_id=?',(pid,))

def mutate(data,operation,callback):
    db=get_db();key=data.get('request_id')
    if not isinstance(key,str) or not 8<=len(key)<=100:raise ValidationError('Brak identyfikatora operacji. Odśwież formularz.')
    fingerprint=hashlib.sha256(json.dumps([operation,data],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    try:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT * FROM bond_requests WHERE request_id=?',(key,)).fetchone()
        if previous:
            if previous['fingerprint']!=fingerprint:raise ValidationError('Identyfikator użyty dla innej operacji. Otwórz nowy formularz.')
            result=json.loads(previous['result']);db.rollback();return result
        result=callback(db)
        db.execute('INSERT INTO bond_requests VALUES(?,?,?)',(key,fingerprint,json.dumps(result)));db.commit();return result
    except Exception:db.rollback();raise

def load(db,bid,data=None):
    row=db.execute(f'SELECT {BOND_COLUMNS} FROM bonds WHERE id=?',(bid,)).fetchone()
    if not row:raise NotFoundError('Nie znaleziono obligacji.')
    portfolio(db,row['portfolio_id'])
    if data is not None and data.get('version')!=row['version']:raise ValidationError('Dane zmieniły się. Odśwież widok przed zapisem.')
    return dict(row,purchase_date=str(row['purchase_date']))

def details(db,bond,as_of=None,assumed_rate=None):
    bond=dict(bond,purchase_date=str(bond['purchase_date']))
    rates=[dict(r) for r in db.execute('SELECT * FROM bond_rates WHERE bond_id=? ORDER BY period',(bond['id'],))]
    events=[dict(r) for r in db.execute('SELECT * FROM bond_events WHERE bond_id=? ORDER BY date,id',(bond['id'],))]
    try:return dict(bond,**estimate(bond,rates,events,as_of,assumed_rate),rates=rates,events=events)
    except (ValueError,TypeError):
        return dict(bond,remaining_quantity=bond['quantity'],nominal_value=bond['principal'],cost_remaining=bond['principal'],
            total_value=bond['principal'],accrued_interest=0,current_period_interest=0,capitalized_interest=0,
            pending_interest=0,estimated_interest_net=0,estimated_value_net=bond['principal'],open_profit=0,
            paid_interest_net=0,current_rate=bond['interest_rate'],periods=[],next_event=None,early_redemption_net=None,
            warnings=['Niepoprawne warunki starszego wpisu. Uzupełnij dane; wycena obejmuje wyłącznie kapitał.'],
            rates=rates,events=events,as_of=(as_of or date.today()).isoformat(),is_estimate=True)

class BondService:
    @staticmethod
    def get_bonds(pid):
        db=get_db()
        return [details(db,dict(r)) for r in db.execute(f'SELECT {BOND_COLUMNS} FROM bonds WHERE portfolio_id=? ORDER BY purchase_date DESC,id DESC',(pid,))]

    @staticmethod
    def insert(db,pid,values,acquisition):
        portfolio(db,pid);account_check(db,values['payout_account_id'])
        if acquisition=='BUY':
            updated=db.execute('UPDATE portfolios SET current_cash=ROUND(current_cash-?,2) WHERE id=? AND current_cash>=?',(values['principal'],pid,values['principal']))
            if updated.rowcount!=1:raise ValidationError('Brak gotówki na zakup. Najpierw zasil portfel transferem.')
        fields=list(values)+['portfolio_id','acquisition']
        bid=db.execute(f"INSERT INTO bonds ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",(*values.values(),pid,acquisition)).lastrowid
        opening=None
        if acquisition=='EXISTING':
            opening=tx(db,pid,bid,'DEPOSIT',values['principal'],values['purchase_date'])
            db.execute('UPDATE portfolios SET total_deposits=ROUND(total_deposits+?,2) WHERE id=?',(values['principal'],pid))
        purchase=tx(db,pid,bid,'BUY',values['principal'],values['purchase_date'],values['quantity'])
        db.execute('''INSERT INTO bond_events(bond_id,kind,date,quantity,net_amount,transaction_id,extra_transaction_id)
            VALUES(?,?,?,?,?,?,?)''',(bid,acquisition,values['purchase_date'],values['quantity'],values['principal'],purchase,opening))
        invalidate(db,pid);return dict(id=bid)

    @staticmethod
    def create(data):
        values=validate(data);acquisition=data.get('acquisition','BUY')
        if acquisition not in ('BUY','EXISTING'):raise ValidationError('Wybierz sposób dodania zakupu.')
        pid=number(data.get('portfolio_id'),'Portfel',1,999999999,True)
        return mutate(data,'create',lambda db:BondService.insert(db,pid,values,acquisition))

    @staticmethod
    def update(bid,data):
        values=validate(data)
        def apply(db):
            bond=load(db,bid,data)
            if bond['status']!='ACTIVE':raise ValidationError('Zamkniętego zakupu nie można zmieniać.')
            paid=db.execute("SELECT 1 FROM bond_events WHERE bond_id=? AND kind IN ('REDEEM','COUPON')",(bid,)).fetchone()
            if paid and any(values[k]!=bond[k] for k in values if k not in ('name','notes','payout_account_id','forecast_enabled')):
                raise ValidationError('Po wypłacie można zmienić nazwę, notatkę i konto planowanych wypłat. Warunki rozliczonych okresów pozostają zapisane.')
            if values['kind']!=bond['kind'] and db.execute('SELECT 1 FROM bond_rates WHERE bond_id=?',(bid,)).fetchone():
                raise ValidationError('Zmiana rodzaju wymaga wyjaśnienia zapisanych stóp okresowych. Nie usuwamy ich automatycznie.')
            for field in ('quantity','purchase_price','principal','purchase_date'):
                if bond['kind']!='LEGACY' and values[field]!=bond[field]:raise ValidationError('Kwota, liczba sztuk i data są księgowane. Anuluj zakup i dodaj poprawny wpis.')
            if bond['kind']=='LEGACY' and values['principal']!=bond['principal']:raise ValidationError('Zachowaj kapitał starszego wpisu. Sprawdź wpłaty przed korektą.')
            account_check(db,values['payout_account_id'])
            db.execute(f"UPDATE bonds SET {','.join(f'{k}=?' for k in values)},version=version+1 WHERE id=?",(*values.values(),bid))
            invalidate(db,bond['portfolio_id']);return dict(id=bid)
        return mutate(data,f'update:{bid}',apply)

    @staticmethod
    def rate(bid,data):
        index=number(data.get('period'),'Okres',2,600,True);rate=number(data.get('rate'),'Oprocentowanie',0,100)
        def apply(db):
            bond=load(db,bid,data)
            if bond['status']!='ACTIVE' or bond['kind']=='LEGACY' or not KINDS[bond['kind']]['variable']:raise ValidationError('Ten zakup nie ma zmiennego oprocentowania.')
            view=details(db,bond);period=next((p for p in view['periods'] if p['period']==index),None)
            if not period:raise ValidationError('Nieprawidłowy okres odsetkowy.')
            if period['start_date']>date.today().isoformat():raise ValidationError('Przyszłą stopę ustaw w symulacji, nie jako potwierdzoną.')
            if any(e['kind'] in ('REDEEM','COUPON') and e['date']>=period['start_date'] for e in view['events']):raise ValidationError('Okres ma rozliczoną wypłatę. Nie zmieniamy jej wyceny wstecz.')
            db.execute('INSERT INTO bond_rates VALUES(?,?,?) ON CONFLICT(bond_id,period) DO UPDATE SET rate=excluded.rate',(bid,index,rate))
            db.execute('UPDATE bonds SET version=version+1 WHERE id=?',(bid,));invalidate(db,bond['portfolio_id']);return dict(id=bid)
        return mutate(data,f'rate:{bid}',apply)

    @staticmethod
    def settle(bid,data):
        when=day(data.get('date'),'Data faktycznej wypłaty').isoformat();net=amount(data.get('net_amount'),'Otrzymana kwota netto',True);kind=data.get('kind')
        if kind not in ('COUPON','REDEEM'):raise ValidationError('Wybierz rodzaj wypłaty.')
        def apply(db):
            bond=load(db,bid,data)
            if bond['status']!='ACTIVE' or bond['kind']=='LEGACY':raise ValidationError('Uzupełnij warunki aktywnego zakupu.')
            if when<bond['purchase_date']:raise ValidationError('Wypłata nie może poprzedzać zakupu.')
            latest=db.execute('SELECT MAX(date) FROM bond_events WHERE bond_id=?',(bid,)).fetchone()[0]
            if latest and when<latest:raise ValidationError('Rozliczaj zdarzenia w kolejności dat.')
            view=details(db,bond,day(when));qty=number(data.get('quantity',view['remaining_quantity']),'Liczba wykupywanych sztuk',1,view['remaining_quantity'],True);index=None
            if kind=='COUPON':
                index=number(data.get('period'),'Okres wypłaty',1,600,True);period=next((p for p in view['periods'] if p['period']==index),None)
                if not period or not KINDS[bond['kind']]['coupons'] or not period['complete'] or period['paid']:raise ValidationError('Wybierz zakończony, nierozliczony okres wypłaty.')
                if qty!=view['remaining_quantity']:raise ValidationError('Wypłata odsetek obejmuje wszystkie pozostałe sztuki zakupu.')
            elif any(p['complete'] and p['pays_cash'] and not p['paid'] for p in view['periods']) and KINDS[bond['kind']]['coupons']:raise ValidationError('Najpierw zapisz wypłacone odsetki za zakończone okresy; potem wykup kapitału.')
            if kind=='REDEEM' and when<bond['maturity_date'] and bond['redemption_fee'] is None:raise ValidationError('Uzupełnij opłatę wcześniejszego wykupu z listu emisyjnego (także gdy wynosi 0).')
            if kind=='REDEEM' and data.get('confirmed_actual') is not True:raise ValidationError('Potwierdź rzeczywisty wykup i kwotę wypłaty.')
            history=data.get('history_only',False)
            transfer=data.get('transfer_to_budget',False)
            if not isinstance(history,bool) or not isinstance(transfer,bool) or (history and transfer):
                raise ValidationError('Wybierz jeden sposób rozliczenia salda wypłaty.')
            profit=0 if kind=='COUPON' else money(net-bond['principal']*qty/bond['quantity'])
            transaction=tx(db,bond['portfolio_id'],bid,'INTEREST' if kind=='COUPON' else 'SELL',net,when,qty,profit)
            extra=None
            if history:
                # The payout has already left the investment account and is
                # included in today's bank balance; record its flow, not cash.
                extra=tx(db,bond['portfolio_id'],bid,'WITHDRAW',net,when)
            else:db.execute('UPDATE portfolios SET current_cash=ROUND(current_cash+?,2) WHERE id=?',(net,bond['portfolio_id']))
            db.execute('INSERT INTO bond_events(bond_id,kind,date,quantity,period,net_amount,transaction_id,extra_transaction_id,notes) VALUES(?,?,?,?,?,?,?,?,?)',(bid,kind,when,qty,index,net,transaction,extra,'Historia bez zmiany sald; wypłata poza portfel już uwzględniona' if history else ''))
            db.execute('UPDATE bonds SET version=version+1 WHERE id=?',(bid,))
            if transfer:
                if not bond['payout_account_id']:raise ValidationError('Ustaw konto wypłaty w warunkach zakupu.')
                from budget_transfer_service import transfer_investment_cash
                transfer_investment_cash(bond['payout_account_id'],bond['portfolio_id'],net,'IN',f"Obligacje: {bond['name']}",date=when,request_id='bond:'+data['request_id'],commit=False)
            invalidate(db,bond['portfolio_id']);return dict(id=bid,received=net)
        return mutate(data,f'settle:{bid}',apply)

    @staticmethod
    def cancel(bid,data):
        def apply(db):
            bond=load(db,bid,data);events=[dict(r) for r in db.execute('SELECT * FROM bond_events WHERE bond_id=?',(bid,))]
            if bond['status']!='ACTIVE' or bond['acquisition']=='LEGACY' or any(e['kind'] not in ('BUY','EXISTING') for e in events):raise ValidationError('Anulować można zakup bez późniejszych wypłat. Starszy wpis wymaga uzgodnienia sald.')
            when=date.today().isoformat();reverse=tx(db,bond['portfolio_id'],bid,'SELL',bond['principal'],when,bond['quantity']);extra=None
            if bond['acquisition']=='BUY':db.execute('UPDATE portfolios SET current_cash=ROUND(current_cash+?,2) WHERE id=?',(bond['principal'],bond['portfolio_id']))
            else:
                extra=tx(db,bond['portfolio_id'],bid,'WITHDRAW',bond['principal'],when)
                db.execute('UPDATE portfolios SET total_deposits=ROUND(total_deposits-?,2) WHERE id=?',(bond['principal'],bond['portfolio_id']))
            db.execute('INSERT INTO bond_events(bond_id,kind,date,transaction_id,extra_transaction_id) VALUES(?,?,?,?,?)',(bid,'CANCEL',when,reverse,extra))
            db.execute("UPDATE bonds SET status='VOID',version=version+1 WHERE id=?",(bid,));invalidate(db,bond['portfolio_id']);return dict(id=bid)
        return mutate(data,f'cancel:{bid}',apply)

    @staticmethod
    def workspace(pid,assumed_rate=None):
        db=get_db();p=portfolio(db,pid);rows=BondService.get_bonds(pid);active=[b for b in rows if b['remaining_quantity'] and b['status']!='VOID']
        summary={key:money(sum(b[key] for b in active)) for key in ('nominal_value','cost_remaining','accrued_interest','estimated_interest_net','capitalized_interest','current_period_interest','total_value','estimated_value_net','open_profit')}
        summary.update(cash=money(p['current_cash']),paid_interest_net=money(sum(b['paid_interest_net'] for b in rows)))
        events=[];forecast=[]
        for b in active:
            if b['kind']=='LEGACY':continue
            projection=details(db,b,day(b['maturity_date'],future=True),assumed_rate)
            for period in projection['periods']:
                if period['paid']:continue
                if period['end_date']<date.today().isoformat() and not period['pays_cash']:continue
                maturity=period['end_date']==b['maturity_date'];cash=period['pays_cash']
                net=projection['estimated_value_net'] if maturity and not KINDS[b['kind']]['coupons'] else money(period['net']+(b['nominal_value'] if maturity else 0)) if cash else 0
                events.append(dict(key=f"bond:{b['id']}:{period['period']}",bond_id=b['id'],portfolio_id=pid,name=b['name'],date=period['end_date'],kind='MATURITY' if maturity else 'COUPON' if cash else 'CAPITALIZATION',net_amount=net,assumed=period['assumed'],payout_account_id=b['payout_account_id'],forecast_enabled=bool(b['forecast_enabled'])))
            for offset in range(13):
                when=shift(date.today(),offset)
                value=details(db,b,when,assumed_rate)
                coupons=sum(p['net'] for p in value['periods'] if p['pays_cash'] and p['end_date']>date.today().isoformat() and p['end_date']<=when.isoformat()) if KINDS[b['kind']]['coupons'] else 0
                projected_value=max(0,money(value['estimated_value_net']-coupons))
                if when.isoformat()>=b['maturity_date']:
                    coupons+=projected_value;projected_value=0
                forecast.append(dict(date=when.isoformat(),bond_id=b['id'],value=projected_value,coupons=money(coupons)))
        return dict(as_of=date.today().isoformat(),items=rows,summary=summary,events=sorted(events,key=lambda e:e['date']),forecast=forecast,kinds=KINDS,warnings=list(dict.fromkeys(w for b in active for w in b['warnings'])))

    @staticmethod
    def preview_import(pid,text):
        portfolio(get_db(),pid)
        if not isinstance(text,str) or len(text)>1000000:raise ValidationError('Plik CSV jest za duży lub niepoprawny.')
        try:
            delimiter=';' if ';' in text.splitlines()[0] else ','
            rows=list(csv.DictReader(io.StringIO(text.lstrip('\ufeff')),delimiter=delimiter))
        except (csv.Error,IndexError):raise ValidationError('Nie udało się odczytać CSV.') from None
        if not 1<=len(rows)<=200:raise ValidationError('Import wymaga od 1 do 200 zakupów.')
        result=[]
        for index,row in enumerate(rows,2):
            row={k:v.replace(',','.') if k in ('purchase_price','interest_rate','redemption_fee','nominal','tax_rate') else v for k,v in row.items() if k is not None and v!=''}
            row.update(portfolio_id=pid,acquisition='EXISTING',forecast_enabled=False)
            try:
                values=validate(row)
                duplicate=get_db().execute("SELECT id FROM bonds WHERE portfolio_id=? AND name=? AND purchase_date=? AND principal=? AND status!='VOID'",(pid,values['name'],values['purchase_date'],values['principal'])).fetchone()
                result.append(dict(line=index,plan=dict(values,forecast_enabled=False,portfolio_id=pid,acquisition='EXISTING'),duplicate=bool(duplicate),error=None))
            except ValidationError as error:result.append(dict(line=index,plan=None,duplicate=False,error=str(error)))
        return dict(rows=result)

    @staticmethod
    def import_rows(data):
        rows=data.get('rows')
        if not isinstance(rows,list) or not 1<=len(rows)<=200:raise ValidationError('Wybierz zakupy do importu.')
        def apply(db):
            ids=[];pid=number(data.get('portfolio_id'),'Portfel',1,999999999,True)
            for row in rows:
                if not isinstance(row,dict):raise ValidationError('Niepoprawny wiersz importu.')
                values=validate(row)
                if db.execute("SELECT 1 FROM bonds WHERE portfolio_id=? AND name=? AND purchase_date=? AND principal=? AND status!='VOID'",(pid,values['name'],values['purchase_date'],values['principal'])).fetchone():raise ValidationError(f"Zakup {values['name']} jest już zapisany. Usuń duplikat z podglądu.")
                ids.append(BondService.insert(db,pid,values,'EXISTING')['id'])
            return dict(ids=ids)
        return mutate(data,'import',apply)

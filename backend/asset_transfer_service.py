"""Internal custody transfers: original cost stays intact, strategies start at entry value."""
import math
import re
from datetime import date, datetime
from uuid import uuid4
from database import get_db
from api.exceptions import ValidationError

IN = 'ASSET_IN'
OUT = 'ASSET_OUT'


def init_schema(db):
    schema=db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'").fetchone()[0]
    if "CHECK" in schema.upper() and 'ASSET_IN' not in schema:
        updated,count=re.subn(r"CHECK\s*\(\s*type\s+IN\s*\(([^)]*)\)\s*\)",
                              lambda m:"CHECK(type IN ("+m.group(1)+", 'ASSET_IN', 'ASSET_OUT'))",schema,flags=re.I)
        if count!=1:raise RuntimeError('Unrecognized transaction type constraint')
        indexes=[r[0] for r in db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='transactions' AND type IN ('index','trigger') AND sql IS NOT NULL")]
        updated=re.sub(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?["`\[]?transactions["`\]]?', 'CREATE TABLE transactions_asset_migration',updated,count=1,flags=re.I)
        columns=','.join('"'+r['name']+'"' for r in db.execute('PRAGMA table_info(transactions)'))
        db.execute(updated)
        db.execute(f'INSERT INTO transactions_asset_migration ({columns}) SELECT {columns} FROM transactions')
        db.execute('DROP TABLE transactions')
        db.execute('ALTER TABLE transactions_asset_migration RENAME TO transactions')
        for statement in indexes:db.execute(statement)
    if 'asset_cost' not in {r['name'] for r in db.execute('PRAGMA table_info(transactions)')}:
        db.execute('ALTER TABLE transactions ADD COLUMN asset_cost REAL')
    db.execute('CREATE TABLE IF NOT EXISTS portfolio_archive_snapshots(portfolio_id INTEGER PRIMARY KEY REFERENCES portfolios(id), archived_at TEXT NOT NULL, data TEXT NOT NULL)')


def strategy_basis(db, parent, sub):
    """Replay the strategy's cost independently of the broker cost ledger."""
    states, profits = {}, {}
    rows = db.execute("SELECT * FROM transactions WHERE portfolio_id=? AND sub_portfolio_id IS ? ORDER BY date(date), CASE WHEN type='SELL' AND length(date)=10 THEN '23:59:59' ELSE substr(date,12) END,id", (parent, sub))
    for r in rows:
        key=r['ticker']; q,c=states.get(key,(0.,0.)); n=float(r['quantity']); amount=float(r['total_value'])
        if r['type'] in ('BUY',IN): q,c=q+n,c+amount
        elif r['type'] in ('SELL',OUT) and q>0:
            cost=c*n/q
            profits[r['id']]=amount-cost if r['type']=='SELL' else 0.
            q,c=max(0.,q-n),max(0.,c-cost)
        states[key]=(q,c if q>1e-8 else 0.)
    return states,profits


def transfer(data, manage_transaction=True, stamp=None):
    db=get_db()
    try:
        pid=data['portfolio_id']; source=data.get('source_id'); target=data.get('target_id')
        if isinstance(pid,bool) or not isinstance(pid,int) or pid<=0: raise ValueError()
        if any(v is not None and (isinstance(v,bool) or not isinstance(v,int) or v<=0) for v in (source,target)): raise ValueError()
        qty=data['quantity']; price=data['price_pln']; expected=data['expected_quantity']
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (qty,price,expected)):raise ValueError()
        if price>1e9 or qty>1e9:raise ValueError()
        ticker=data['ticker']
        if not isinstance(ticker,str) or not ticker:raise ValueError()
    except (KeyError,ValueError,TypeError):
        raise ValidationError('Podaj portfel, źródło, cel, liczbę jednostek i dodatnią wycenę jednej jednostki w PLN.') from None
    if source==target:raise ValidationError('Wybierz inne konto docelowe.')
    try:
        if manage_transaction: db.execute('BEGIN IMMEDIATE')
        parent=db.execute('SELECT * FROM portfolios WHERE id=?', (pid,)).fetchone()
        if not parent or parent['parent_portfolio_id'] or parent['is_archived'] or parent['account_type'] not in ('IKE','IKZE','STANDARD'):
            raise ValidationError('Wybierz aktywny główny portfel akcji.')
        for scope in (source,target):
            if scope is not None:
                row=db.execute('SELECT * FROM portfolios WHERE id=?',(scope,)).fetchone()
                if not row or row['parent_portfolio_id']!=pid or row['is_archived']:raise ValidationError('Podkonto musi należeć do tego samego portfela i być aktywne.')
        h=db.execute('SELECT * FROM holdings WHERE portfolio_id=? AND sub_portfolio_id IS ? AND ticker=?',(pid,source,ticker)).fetchone()
        if not h or abs(float(h['quantity'])-expected)>1e-8:raise ValidationError('Pozycja zmieniła się. Odśwież portfel przed przeniesieniem.')
        if qty>float(h['quantity'])+1e-9:raise ValidationError('Nie masz tylu jednostek na koncie źródłowym.')
        original=float(h['total_cost'])*qty/float(h['quantity']); value=price*qty
        stamp=stamp or datetime.now().isoformat(sep=' ',timespec='seconds'); transfer_id='asset:'+str(uuid4())
        for scope,kind in ((source,OUT),(target,IN)):
            db.execute('''INSERT INTO transactions(portfolio_id,sub_portfolio_id,ticker,type,quantity,price,total_value,
                date,transfer_id,asset_cost,realized_profit,commission)
                VALUES(?,?,?,?,?,?,?,?,?,?,0,0)''',(pid,scope,ticker,kind,qty,price,value,stamp,transfer_id,original))
        remaining=float(h['quantity'])-qty
        if remaining<1e-8:db.execute('DELETE FROM holdings WHERE id=?',(h['id'],))
        else:db.execute('UPDATE holdings SET quantity=?,total_cost=?,average_buy_price=? WHERE id=?',
                        (remaining,float(h['total_cost'])-original,(float(h['total_cost'])-original)/remaining,h['id']))
        dest=db.execute('SELECT * FROM holdings WHERE portfolio_id=? AND sub_portfolio_id IS ? AND ticker=?',(pid,target,ticker)).fetchone()
        if dest:
            if (dest['currency'] or 'PLN')!=(h['currency'] or 'PLN'):raise ValidationError('Waluta pozycji docelowej nie jest zgodna.')
            newq=float(dest['quantity'])+qty; cost=float(dest['total_cost'])+original
            db.execute('UPDATE holdings SET quantity=?,total_cost=?,average_buy_price=? WHERE id=?',(newq,cost,cost/newq,dest['id']))
        else:
            db.execute('''INSERT INTO holdings(portfolio_id,sub_portfolio_id,ticker,quantity,total_cost,average_buy_price,
               company_name,sector,industry,currency,instrument_currency,auto_fx_fees,avg_buy_price_native,avg_buy_fx_rate)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(pid,target,ticker,qty,original,original/qty,h['company_name'],h['sector'],h['industry'],h['currency'],h['instrument_currency'],h['auto_fx_fees'],h['avg_buy_price_native'],h['avg_buy_fx_rate']))
        for table in ('portfolio_history_cache','analytics_cache'):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                db.execute('DELETE FROM '+table)
        if manage_transaction: db.commit()
    except Exception:
        if manage_transaction: db.rollback()
        raise
    from portfolio_service import PortfolioService
    if manage_transaction:
        for scope in (pid,source,target):
            if scope:PortfolioService.clear_cache(scope)
    return {'transfer_id':transfer_id,'date':stamp,'quantity':qty,'entry_value':value,'original_cost':original}

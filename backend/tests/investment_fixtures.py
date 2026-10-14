"""Shared regression fixtures; use only the disposable database supplied by tests."""


def transaction(db,pid,kind,amount,qty=1,ticker='CASH',sub=None,day='2024-01-01'):
    return db.execute('''INSERT INTO transactions(portfolio_id,sub_portfolio_id,ticker,type,quantity,price,total_value,date)
        VALUES(?,?,?,?,?,?,?,?)''',(pid,sub,ticker,kind,qty,amount/qty if qty else 0,amount,day)).lastrowid


def parent(db,cash=1000):
    pid=db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES('Audit','STANDARD',?)",(cash,)).lastrowid
    transaction(db,pid,'DEPOSIT',cash)
    db.execute("INSERT INTO symbol_mappings(symbol_input,ticker,currency) VALUES('AUDIT.WA','AUDIT.WA','PLN')")
    db.commit();return pid

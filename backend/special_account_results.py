"""Read-only period valuation of PPK and bond accounts, using dated records only."""
import json
import math
from datetime import date, timedelta
from decimal import Decimal

from investment_math import modified_dietz
from bond_service import BOND_COLUMNS, details
from modules.ppk.ppk_calculation import PPKCalculation
from portfolio_valuation_service import PortfolioValuationService


def build_special_model(db, portfolio, end):
    pid, kind = portfolio['id'], portfolio['account_type']
    warnings = []
    rows = [dict(r) for r in db.execute('''SELECT *, date(date) AS day FROM transactions
        WHERE portfolio_id=? AND date(date)<=? ORDER BY date(date),id''', (pid, end.isoformat()))]
    flows = [(date.fromisoformat(r['day']), float(r['total_value']) * (1 if r['type']=='DEPOSIT' else -1))
             for r in rows if r['type'] in ('DEPOSIT', 'WITHDRAW') ]
    basis = 'Wycena obligacji netto według zapisanych warunków, wraz z gotówką.'
    contributions = []
    prices = []
    bonds = []
    if kind == 'PPK':
        basis = 'Wartość jednostek brutto. Wpłaty pracownika i pracodawcy są kapitałem, nie wynikiem funduszu.'
        contributions = [dict(r) for r in db.execute('''SELECT *,date(date) AS day FROM ppk_transactions
            WHERE portfolio_id=? AND date(date)<=? ORDER BY date(date),id''', (pid,end.isoformat()))]
        cache = db.execute("SELECT data FROM ppk_weekly_history WHERE fund_id='61777738'").fetchone()
        try:
            prices = sorted([(date.fromisoformat(p['week']),float(p['price'])) for p in json.loads(cache['data'] if cache else '[]')
                             if math.isfinite(float(p['price'])) and float(p['price'])>0])
        except (ValueError,TypeError,KeyError):
            warnings.append('Nie można odczytać zapisanej historii ceny PPK.')
        flows += [(date.fromisoformat(r['day']), (float(r['employee_units'])+float(r['employer_units']))*float(r['price_per_unit']))
                  for r in contributions]
    else:
        bonds = [dict(r) for r in db.execute(f'SELECT {BOND_COLUMNS} FROM bonds WHERE portfolio_id=?', (pid,))]

    price_dates = {}
    warnings_by_date={}
    def value(day):
        issues=warnings_by_date.setdefault(day.isoformat(),[])
        cash = sum(PortfolioValuationService.cash_delta(r) for r in rows if r['day']<=day.isoformat())
        if kind == 'PPK':
            active = [r for r in contributions if r['day']<=day.isoformat()]
            if not active:
                return round(cash,2)
            eligible = [(d,p) for d,p in prices if d<=day]
            if not eligible:
                issues.append(f'PPK: brak ceny jednostki na {day.isoformat()} lub wcześniej.')
                return None
            priced_on, price = eligible[-1]
            price_dates[day.isoformat()] = priced_on.isoformat()
            if (day-priced_on).days>7:
                issues.append(f'PPK: wycena na {day.isoformat()} używa ceny z {priced_on.isoformat()} (starszej niż 7 dni).')
            return round(cash+PPKCalculation.calculate_metrics(active,Decimal(str(price)))['totalCurrentValue'],2)
        total = cash
        for bond in bonds:
            # Cancellation reverses the acquisition ledger; it must also remove the asset.
            if bond['status']=='VOID' or bond['purchase_date']>day.isoformat():
                continue
            model = details(db,bond,as_of=day)
            issues.extend(f"{bond['name']}: {w}" for w in model['warnings'])
            if bond['kind']=='LEGACY':
                issues.append(f"{bond['name']}: uzupełnij warunki starego zapisu przed wyliczeniem wyniku.")
            total += model['estimated_value_net']
        return round(total,2)

    def warnings_for(day):
        return list(dict.fromkeys([*warnings,*warnings_by_date.get(day.isoformat(),[])]))
    def positions(day):
        return {f"BOND:{bond['id']}":0 if bond['status']=='VOID' or bond['purchase_date']>day.isoformat()
                else details(db,bond,as_of=day)['remaining_quantity'] for bond in bonds}
    return {'value': value, 'flows': flows, 'warnings': warnings,'warnings_for':warnings_for,'positions':positions, 'basis': basis,
            'price_dates': price_dates, 'first_record': min([d for d, _ in flows] + [date.fromisoformat(b['purchase_date']) for b in bonds], default=end)}


def analyze_special(db, portfolio, first, end):
    model = build_special_model(db, portfolio, end)
    value = model['value']
    flows = [(day, amount) for day, amount in model['flows'] if day >= first]
    opening, closing = value(first-timedelta(days=1)), value(end)
    warnings=model['warnings_for'](first-timedelta(days=1))+model['warnings_for'](end)
    if end == date.today():
        rows = [dict(r) for r in db.execute('SELECT * FROM transactions WHERE portfolio_id=? AND date(date)<=?', (portfolio['id'],end.isoformat()))]
        cash = sum(PortfolioValuationService.cash_delta(r) for r in rows)
        stored = float(portfolio['current_cash'] or 0)
        if abs(stored-cash)>.01:
            warnings.append('Obecna gotówka nie zgadza się z historią operacji. Wynik jest wstrzymany do wyjaśnienia różnicy.')
    warnings = list(dict.fromkeys(warnings))
    net = sum(amount for _,amount in flows)
    estimate = round(closing-opening-net,2) if opening is not None and closing is not None else None
    valid = estimate is not None and not warnings
    return dict(opening_value=opening,closing_value=closing,profit=estimate if valid else None,
        estimated_profit=estimate,return_percent=modified_dietz(opening,closing,flows,first,end) if valid else None,
        status='ok' if valid else 'incomplete',warnings=warnings,basis=model['basis'],price_dates=model['price_dates'])

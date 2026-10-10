"""Read-only estimates. Never book estimated interest or future rate assumptions."""
import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

KINDS = {
    'OTS': dict(label='OTS · 3 miesiące', months=3, interval=3, capitalizes=False, coupons=False, variable=False),
    'ROR': dict(label='ROR · 1 rok', months=12, interval=1, capitalizes=False, coupons=True, variable=True),
    'DOR': dict(label='DOR · 2 lata', months=24, interval=1, capitalizes=False, coupons=True, variable=True),
    'TOS': dict(label='TOS · 3 lata', months=36, interval=12, capitalizes=True, coupons=False, variable=False),
    'COI': dict(label='COI · 4 lata', months=48, interval=12, capitalizes=False, coupons=True, variable=True),
    'EDO': dict(label='EDO · 10 lat', months=120, interval=12, capitalizes=True, coupons=False, variable=True),
    'ROS': dict(label='ROS · 6 lat', months=72, interval=12, capitalizes=True, coupons=False, variable=True),
    'ROD': dict(label='ROD · 12 lat', months=144, interval=12, capitalizes=True, coupons=False, variable=True),
    'CUSTOM': dict(label='Własna · stała stopa, wypłata przy wykupie', months=None, interval=12, capitalizes=False, coupons=False, variable=False),
}

def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))

def shift(day, months):
    y, m = divmod(day.year * 12 + day.month - 1 + months, 12)
    return date(y, m + 1, min(day.day, calendar.monthrange(y, m + 1)[1]))

def estimate(bond, rates=(), events=(), as_of=None, assumed_rate=None):
    today = as_of or date.today()
    purchase = date.fromisoformat(str(bond['purchase_date']))
    original = int(bond['quantity'])
    redeemed = sum(e['quantity'] for e in events if e['kind']=='REDEEM' and e['date']<=today.isoformat())
    remaining = max(0, original-redeemed) if bond['status']!='VOID' else 0
    nominal = float(bond['nominal'] or bond['principal'])
    cost = float(bond['principal']) * remaining / original
    tax = float(bond['tax_rate']) / 100
    paid = sum(e['net_amount'] for e in events if e['kind']=='COUPON' and e['date']<=today.isoformat())
    maturity = date.fromisoformat(bond['maturity_date']) if bond['maturity_date'] else None
    warnings, periods = [], []
    if bond['kind']=='LEGACY':
        earned = nominal * float(bond['interest_rate'])/100 * max(0,(today-purchase).days)/365
        warnings.append('Starszy wpis: uproszczone odsetki bez terminu wykupu. Uzupełnij warunki i sprawdź księgowanie kapitału.')
        capitalized, pending, current, current_rate = 0.,earned*remaining,earned*remaining,float(bond['interest_rate'])
    else:
        spec = KINDS[bond['kind']]
        known = {r['period']:float(r['rate']) for r in rates}
        known[1] = float(bond['interest_rate'])
        unit_base, accumulated, pending, current, capitalized = nominal,0.,0.,0.,0.
        current_rate = known[1]
        paid_periods = {e['period'] for e in events if e['kind']=='COUPON' and e['date']<=today.isoformat()}
        missing = []
        for index in range(1, 601):
            start = shift(purchase,(index-1)*spec['interval'])
            if start>=maturity: break
            full_end = shift(purchase,index*spec['interval'])
            end = min(full_end,maturity)
            assumed = spec['variable'] and index not in known
            rate = known.get(index, float(assumed_rate) if assumed_rate is not None and assumed else current_rate)
            if not spec['variable']:rate=known[1]
            fraction = spec['interval']/12 * (end-start).days/(full_end-start).days
            full_interest = unit_base*rate/100*fraction
            elapsed = max(0,min((today-start).days,(end-start).days))
            partial = full_interest*elapsed/(end-start).days
            if start<=today:
                current_rate=rate
                if assumed:missing.append(index)
            complete = end<=today
            coupon_paid = index in paid_periods
            if complete:
                if spec['capitalizes']:
                    capitalized+=full_interest
                elif spec['coupons']:
                    if not coupon_paid:pending+=money(full_interest)*remaining
                else:accumulated+=full_interest
            elif start<=today:
                current=partial*remaining
            periods.append(dict(period=index,start_date=start.isoformat(),end_date=end.isoformat(),rate=rate,
                assumed=assumed,gross=money(money(full_interest)*remaining),
                net=money(money(full_interest*(1-tax))*remaining),capitalizes=spec['capitalizes'],
                pays_cash=spec['coupons'] or end==maturity,paid=coupon_paid,complete=complete))
            # Future schedule amounts also use each preceding capitalization;
            # only completed periods contribute to today's accrued value.
            if spec['capitalizes']:unit_base+=full_interest
        if missing:warnings.append('Brak zapisanej stopy dla okresów '+', '.join(map(str,missing))+'. Wycena używa założonego oprocentowania.')
        # Coupon receivables remain in assets until an actual payout is recorded.
        pending+=current
        capitalized*=remaining
        if not spec['capitalizes'] and not spec['coupons']:pending+=accumulated*remaining
    if purchase>today:warnings.append('Przyszła data zakupu; sprawdź starszy wpis.')
    earned=capitalized+pending
    net_earned=money(earned*(1-tax))
    gross_value=money(nominal*remaining+earned)
    fee=None if bond['redemption_fee'] is None else money(float(bond['redemption_fee'])*remaining)
    if maturity and today>=maturity:fee=0.
    if fee is not None and bond.get('fee_policy','CAP_INTEREST')!='FULL':
        policy=bond.get('fee_policy','CAP_INTEREST')
        interval=KINDS.get(bond['kind'],{}).get('interval',12)
        cap=policy=='CAP_INTEREST' or (policy=='FIRST_PERIOD' and today<shift(purchase,interval))
        if cap:fee=min(fee,max(0,current if bond['kind']=='COI' else earned))
    early_net=None if fee is None else money(nominal*remaining+earned-fee-max(0,earned-fee)*tax)
    status = 'VOID' if bond['status']=='VOID' else 'CLOSED' if remaining==0 else 'MATURED' if maturity and today>=maturity else 'ACTIVE'
    next_event=next((p for p in periods if (p['end_date']>today.isoformat() or (p['pays_cash'] and not p['paid'] and not p['capitalizes']))),None) if remaining else None
    return dict(remaining_quantity=remaining,nominal_value=money(nominal*remaining),cost_remaining=money(cost),
        accrued_interest=money(earned),current_period_interest=money(current),capitalized_interest=money(capitalized),
        pending_interest=money(pending),estimated_interest_net=net_earned,total_value=gross_value,
        estimated_value_net=money(nominal*remaining+net_earned),open_profit=money(gross_value-cost),
        paid_interest_net=money(paid),current_rate=current_rate,status=status,periods=periods,
        next_event=next_event,early_redemption_net=early_net,early_redemption_fee=fee,
        warnings=warnings,as_of=today.isoformat(),is_estimate=True)

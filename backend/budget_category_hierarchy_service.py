"""Two-level budget categories; parent limits are shared, never additive."""
import calendar
from collections import defaultdict

from api.exceptions import NotFoundError, ValidationError


def category_options(db, include_unassigned=True):
    rows = [dict(r) for r in db.execute('SELECT * FROM budget_categories_v2 ORDER BY sort_order,id')]
    by_id = {r['id']: r for r in rows}
    children = defaultdict(list)
    for row in rows:
        if row['parent_id']:
            children[row['parent_id']].append(row)
    result = []
    for root in rows:
        if root['parent_id']:
            continue
        for row in [root, *children[root['id']]]:
            if row['is_unassigned'] and not include_unassigned:
                continue
            parent = by_id.get(row['parent_id'])
            path = f"{parent['name']} › {row['name']}" if parent else row['name']
            result.append({**row, 'parent_name': parent['name'] if parent else None,
                           'path': path, 'has_children': bool(children[row['id']]),
                           'selection_label': path if parent or not children[row['id']] else path + ' › Ogólnie'})
    return result


def plan_amounts(options, manual, bills):
    """Reduce integer cents from children to roots, retaining each own manual cap."""
    amounts = {c['id']: max(manual.get(c['id'], 0), bills.get(c['id'], 0)) for c in options}
    for root in options:
        if root['parent_id'] is None:
            child_plan = sum(amounts[c['id']] for c in options if c['parent_id'] == root['id'])
            amounts[root['id']] = max(manual.get(root['id'], 0), bills.get(root['id'], 0) + child_plan)
    return amounts


def category_workspace(db, month, through=None, pln_only=False):
    options = category_options(db)
    end = through or f"{month}-{calendar.monthrange(*map(int, month.split('-')))[1]:02d}"
    currency = " AND UPPER(COALESCE(a.currency,'PLN'))='PLN'" if pln_only else ''
    spent = dict(db.execute('''SELECT l.category_id,SUM(CASE WHEN e.kind='EXPENSE' THEN l.amount_cents ELSE -l.amount_cents END) FROM budget_entry_lines_v2 l
        JOIN budget_entries_v2 e ON e.id=l.entry_id JOIN budget_accounts a ON a.id=e.account_id
        WHERE (e.kind='EXPENSE' OR EXISTS(SELECT 1 FROM budget_purchase_refunds r WHERE r.entry_id=e.id)) AND e.date BETWEEN ? AND ?''' + currency + ' GROUP BY l.category_id',
        (month+'-01', end)))
    manual = dict(db.execute('SELECT category_id,amount_cents FROM budget_plans_v2 WHERE month=?', (month,)))
    actual_spent = dict(spent)
    from budget_bill_funding import category_coverage
    coverage, settled = category_coverage(db,month)
    for category_id,amount in settled.items():
        spent[category_id]=spent.get(category_id,0)-amount
    from budget_media_service import category_targets, category_adjustments
    media = category_targets(db,month)
    # The envelope's month override is authoritative for its dedicated category.
    # A former manual limit must not silently undo a smaller monthly correction.
    for category_id in media: manual[category_id]=0
    for category_id,amount in category_adjustments(db,month,end,pln_only).items():
        spent[category_id]=spent.get(category_id,0)+amount
    from budget_bill_schedule import category_bill_cents
    from budget_rollover_service import carries
    bills = category_bill_cents(db,month,pln_only)
    for category_id,amount in media.items(): bills[category_id]=bills.get(category_id,0)+amount
    from budget_loan_plan_service import items as loan_items
    loan_rows,_=loan_items(db,month)
    for loan in loan_rows:
        if loan['category_id'] is not None:
            bills[loan['category_id']]=bills.get(loan['category_id'],0)+round(loan['amount']*100)
    # Compute gross shared caps first, then remove the part already earmarked.
    # Settled earmarks also leave category spending, keeping payment neutral.
    gross_bills={key:value+coverage.get(key,0) for key,value in bills.items()}
    for key,value in coverage.items(): gross_bills.setdefault(key,value)
    planned = plan_amounts(options, manual, gross_bills)
    for row in options:
        ids=[row['id'],*[c['id'] for c in options if c['parent_id']==row['id']]]
        planned[row['id']]=max(0,planned[row['id']]-sum(coverage.get(i,0) for i in ids))
    carry = carries(db,month,options)
    for category_id, amount in carry.items():
        planned[category_id] += amount
    result = []
    for row in options:
        category_id = row['id']
        ids = [category_id, *[c['id'] for c in options if c['parent_id'] == category_id]]
        used = sum(spent.get(i, 0) for i in ids)
        result.append({**row, 'is_unassigned': bool(row['is_unassigned']),
            'manual_plan': manual.get(category_id, 0)/100, 'planned_bills': sum(bills.get(i, 0) for i in ids)/100,
            'reserve_covered': sum(coverage.get(i,0) for i in ids)/100,
            'reserve_settled': sum(settled.get(i,0) for i in ids)/100,
            'carryover': carry.get(category_id,0)/100,
            'monthly_reserve_plan': sum(media.get(i,0) for i in ids)/100,
            'monthly_reserve_managed': category_id in media,
            'actual_spent': sum(actual_spent.get(i,0) for i in ids)/100,
            'direct_planned_bills': bills.get(category_id, 0)/100,
            'children_plan': sum(planned[i] for i in ids[1:])/100,
            'planned': planned[category_id]/100, 'direct_spent': spent.get(category_id, 0)/100,
            'spent': used/100, 'remaining': (planned[category_id]-used)/100})
    return result


def save_category(db, data, category_id=None):
    from routes_budget_workspace import positive_id, text_field
    from budget_category_service import require_version
    name = text_field(data.get('name'), 'Nazwa kategorii', 100)
    parent_id = positive_id(data['parent_id'], 'Kategoria główna') if data.get('parent_id') is not None else None
    db.execute('BEGIN IMMEDIATE')
    try:
        if parent_id and db.execute('SELECT 1 FROM budget_reserves WHERE category_id=? AND monthly_amount_cents IS NOT NULL AND open_ended=0 AND is_archived=0',(parent_id,)).fetchone():
            raise ValidationError('Miesięczna pula wymaga osobnej kategorii. Dodaj kolejną kategorię obok niej, np. Woda obok Prądu.')
        current = None
        if category_id is not None:
            current = db.execute('SELECT * FROM budget_categories_v2 WHERE id=?', (category_id,)).fetchone()
            if not current:
                raise NotFoundError('Kategoria nie istnieje.')
            require_version(current, data.get('version'))
            if current['is_unassigned']:
                raise ValidationError('Kategoria do przypisania jest zarządzana przez aplikację.')
        if any(r['id'] != category_id and r['name'].casefold() == name.casefold()
               for r in db.execute('SELECT id,name FROM budget_categories_v2')):
            raise ValidationError('Taka kategoria już istnieje.')
        icon = current['icon'] if current else 'Shapes'
        if parent_id:
            parent = db.execute('SELECT * FROM budget_categories_v2 WHERE id=?', (parent_id,)).fetchone()
            if not parent:
                raise NotFoundError('Kategoria główna nie istnieje.')
            if parent_id == category_id or parent['parent_id'] or parent['is_unassigned']:
                raise ValidationError('Wybierz kategorię główną. Budżet obsługuje dwa poziomy kategorii.')
            if category_id and db.execute('SELECT 1 FROM budget_categories_v2 WHERE parent_id=?', (category_id,)).fetchone():
                raise ValidationError('Kategoria z podkategoriami musi pozostać kategorią główną.')
            if category_id and db.execute("SELECT 1 FROM budget_category_policies WHERE category_id=? AND mode!='RESET'", (category_id,)).fetchone():
                raise ValidationError('Najpierw ustaw zerowanie niewykorzystanego limitu tej kategorii, potem przenieś ją do podkategorii.')
            icon = parent['icon']
        if current:
            db.execute('UPDATE budget_categories_v2 SET name=?,parent_id=?,icon=?,version=version+1 WHERE id=?',
                       (name, parent_id, icon, category_id))
        else:
            order = db.execute('SELECT COALESCE(MAX(sort_order),-1)+1 FROM budget_categories_v2').fetchone()[0]
            category_id = db.execute('INSERT INTO budget_categories_v2(name,parent_id,icon,sort_order) VALUES (?,?,?,?)',
                                     (name, parent_id, icon, order)).lastrowid
        db.commit()
        return {'id': category_id}
    except Exception:
        db.rollback()
        raise

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from database import get_db

class LoanService:
    @staticmethod
    def get_loan_details(loan_id):
        db = get_db()
        loan = db.execute('SELECT * FROM loans WHERE id = ?', (loan_id,)).fetchone()
        if not loan:
            return None
        return dict(loan)

    @staticmethod
    def get_loan_rates(loan_id):
        db = get_db()
        rates = db.execute(
            'SELECT * FROM loan_rates WHERE loan_id = ? ORDER BY valid_from_date ASC',
            (loan_id,)
        ).fetchall()
        return [dict(r) for r in rates]

    @staticmethod
    def get_loan_overpayments(loan_id):
        db = get_db()
        overpayments = db.execute(
            'SELECT * FROM loan_overpayments WHERE loan_id = ? ORDER BY date ASC',
            (loan_id,)
        ).fetchall()
        return [dict(o) for o in overpayments]

    @staticmethod
    def calculate_schedule(loan, rates, overpayments, is_baseline=False, monthly_overpayment=0.0, monthly_overpayment_strategy='REDUCE_TERM'):
        schedule = []
        
        # Initial values
        remaining_balance = float(loan['original_amount'])
        start_date = datetime.strptime(str(loan['start_date']), '%Y-%m-%d').date()
        duration_months = loan['duration_months']
        installment_type = loan['installment_type']
        
        total_interest = 0.0
        
        # Track interest paid up to today for "Saved to Date" calculation
        today = date.today()
        interest_paid_to_date = 0.0
        
        # Sort rates and overpayments by date just in case
        sorted_rates = sorted(rates, key=lambda x: str(x['valid_from_date']))
        sorted_overpayments = sorted(overpayments, key=lambda x: str(x['date']))
        
        # Add Month 0 (Initial State)
        schedule.append({
            'month': 0,
            'date': start_date.strftime('%Y-%m-%d'),
            'interest_rate': 0.0, # Or initial rate if available, but 0 is fine for initial state
            'installment': 0.0,
            'principal_part': 0.0,
            'interest_part': 0.0,
            'overpayment': 0.0,
            'remaining_balance': round(remaining_balance, 2),
            'overpayment_type': None
        })

        # We start from month 1
        payment_date = start_date + relativedelta(months=1)
        
        month_counter = 1
        
        # State tracking for "Sticky Installment" logic (Shorten Term Strategy)
        current_installment_amount = 0.0
        prev_active_rate = -1.0
        
        # Safety break: 2x duration
        while remaining_balance > 0.01 and month_counter <= duration_months * 2:
            # 1. Determine active interest rate for this period
            active_rate = 0.0
            valid_rate = None
            for rate in sorted_rates:
                rate_date = datetime.strptime(str(rate['valid_from_date']), '%Y-%m-%d').date()
                if rate_date <= payment_date:
                    valid_rate = rate
                else:
                    break
            
            if valid_rate:
                active_rate = float(valid_rate['interest_rate'])
            
            # Monthly rate
            monthly_rate = active_rate / 100 / 12
            
            # 2. Handle Overpayments (To decide installment calculation strategy)
            month_overpayment = 0.0
            overpayment_type = 'REDUCE_TERM' # Default strategy
            
            # a. One-off overpayments
            prev_payment_date = payment_date - relativedelta(months=1)
            if month_counter == 1:
                prev_payment_date = start_date
            
            current_month_ops = []
            for op in sorted_overpayments:
                op_date = datetime.strptime(str(op['date']), '%Y-%m-%d').date()
                if prev_payment_date < op_date <= payment_date:
                    current_month_ops.append(op)
            
            # Apply One-Off Overpayments (Mid-Month Injection)
            for op in current_month_ops:
                op_amount = float(op['amount'])
                op_date_str = str(op['date'])
                op_type = op.get('type')
                
                if op_type == 'REDUCE_INSTALLMENT':
                    overpayment_type = 'REDUCE_INSTALLMENT'
                
                # Apply overpayment immediately
                remaining_balance -= op_amount
                month_overpayment += op_amount # Track for this month's total, but we inject a separate point
                
                # Inject mid-month data point
                schedule.append({
                    'month': month_counter, # Same month index
                    'date': op_date_str,
                    'interest_rate': active_rate,
                    'installment': 0.0,
                    'principal_part': round(op_amount, 2),
                    'interest_part': 0.0,
                    'overpayment': round(op_amount, 2),
                    'remaining_balance': round(max(0, remaining_balance), 2),
                    'overpayment_type': op_type,
                    'is_mid_month': True # Flag to distinguish
                })

            # b. Monthly Recurring Overpayment (Simulated Future Only)
            if not is_baseline and payment_date > today and monthly_overpayment > 0:
                 # Future monthly overpayments are applied ON the payment date, so no mid-month injection needed
                 month_overpayment_simulated = monthly_overpayment
                 if monthly_overpayment_strategy == 'REDUCE_INSTALLMENT':
                     overpayment_type = 'REDUCE_INSTALLMENT'
            else:
                 month_overpayment_simulated = 0.0

            # 3. Determine Installment Amount
            months_remaining = max(1, duration_months - month_counter + 1)
            
            # Check if rate changed or first month
            rate_changed = (active_rate != prev_active_rate)
            
            should_recalculate = False
            if month_counter == 1:
                should_recalculate = True
            elif is_baseline:
                should_recalculate = True 
            elif rate_changed:
                should_recalculate = True
            
            # For DECREASING installments, we always calculate Principal + Interest
            if installment_type == 'DECREASING':
                principal_part = remaining_balance / months_remaining
                interest_payment = remaining_balance * monthly_rate
                base_installment = principal_part + interest_payment
            else: # EQUAL (Annuity)
                if should_recalculate:
                    if monthly_rate > 0:
                        factor = (1 + monthly_rate) ** months_remaining
                        if factor == 1:
                             current_installment_amount = remaining_balance / months_remaining
                        else:
                            current_installment_amount = remaining_balance * monthly_rate * factor / (factor - 1)
                    else:
                        # 0% Interest Rate Case
                        current_installment_amount = remaining_balance / months_remaining
                
                base_installment = current_installment_amount
                interest_payment = remaining_balance * monthly_rate
                principal_part = base_installment - interest_payment

            prev_active_rate = active_rate
            
            # 4. Apply Regular Payment (and Simulated Monthly Overpayment)
            # Note: One-off overpayments were already subtracted from remaining_balance above
            
            total_regular_principal = principal_part + month_overpayment_simulated
            
            # Cap at remaining balance
            if total_regular_principal > remaining_balance:
                total_regular_principal = remaining_balance
            
            final_regular_principal = min(principal_part, total_regular_principal)
            final_simulated_overpayment = total_regular_principal - final_regular_principal
            
            final_installment = final_regular_principal + interest_payment

            remaining_balance -= total_regular_principal
            total_interest += interest_payment
            
            # Handle REDUCE_INSTALLMENT Strategy (Recalculate for NEXT month)
            # Check if any ONE-OFF overpayment this month triggered this OR if monthly strategy is active
            if overpayment_type == 'REDUCE_INSTALLMENT' and (month_overpayment > 0 or month_overpayment_simulated > 0) and remaining_balance > 0:
                 # Remaining months for the NEXT period calculation
                 remaining_months_for_recalc = max(1, duration_months - month_counter)
                 
                 if monthly_rate > 0:
                    factor = (1 + monthly_rate) ** remaining_months_for_recalc
                    if factor == 1:
                         current_installment_amount = remaining_balance / remaining_months_for_recalc
                    else:
                        current_installment_amount = remaining_balance * monthly_rate * factor / (factor - 1)
                 else:
                    # 0% Interest Rate Case
                    current_installment_amount = remaining_balance / remaining_months_for_recalc

            # Track interest paid up to today
            if payment_date <= today:
                interest_paid_to_date += interest_payment
            
            schedule.append({
                'month': month_counter,
                'date': payment_date.strftime('%Y-%m-%d'),
                'interest_rate': active_rate,
                'installment': round(final_installment, 2),
                'principal_part': round(final_regular_principal, 2),
                'interest_part': round(interest_payment, 2),
                'overpayment': round(final_simulated_overpayment, 2), # Only simulated monthly OP here
                'remaining_balance': round(max(0, remaining_balance), 2),
                'overpayment_type': None # Standard payment
            })
            
            month_counter += 1
            # Calculate next payment date based on original start date to preserve day of month
            payment_date = start_date + relativedelta(months=month_counter)
            
        return schedule, round(total_interest, 2), round(interest_paid_to_date, 2)

    @staticmethod
    def generate_amortization_schedule(loan_id, simulation_overpayments=None, monthly_overpayment=0.0, monthly_overpayment_strategy='REDUCE_TERM'):
        loan = LoanService.get_loan_details(loan_id)
        if not loan:
            return None
            
        rates = LoanService.get_loan_rates(loan_id)
        db_overpayments = LoanService.get_loan_overpayments(loan_id)
        
        # 1. Baseline Schedule (No overpayments)
        baseline_schedule, baseline_total_interest, baseline_interest_to_date = LoanService.calculate_schedule(
            loan, rates, [], is_baseline=True
        )
        
        # 2. Actual Schedule (Only DB overpayments)
        actual_schedule, actual_total_interest, actual_interest_to_date = LoanService.calculate_schedule(
            loan, rates, db_overpayments, is_baseline=False, monthly_overpayment=0.0
        )
        
        # 3. Simulated Schedule (DB + Simulated Monthly + Simulated One-offs)
        combined_overpayments = db_overpayments.copy()
        if simulation_overpayments:
            for sim_op in simulation_overpayments:
                 combined_overpayments.append(sim_op)
        
        simulated_schedule, simulated_total_interest, simulated_interest_to_date = LoanService.calculate_schedule(
            loan, rates, combined_overpayments, is_baseline=False, 
            monthly_overpayment=monthly_overpayment,
            monthly_overpayment_strategy=monthly_overpayment_strategy
        )
        
        # Calculate months saved (counting only actual installment payments)
        baseline_months = len([p for p in baseline_schedule if p['installment'] > 0])
        actual_months = len([p for p in actual_schedule if p['installment'] > 0])
        simulated_months = len([p for p in simulated_schedule if p['installment'] > 0])
        
        return {
            'loan': loan,
            'baseline': {
                'schedule': baseline_schedule,
                'total_interest': baseline_total_interest
            },
            'actual_metrics': {
                'interest_saved': round(baseline_total_interest - actual_total_interest, 2),
                'months_saved': baseline_months - actual_months,
                'interest_saved_to_date': round(baseline_interest_to_date - actual_interest_to_date, 2)
            },
            'simulated_metrics': {
                'interest_saved': round(baseline_total_interest - simulated_total_interest, 2),
                'months_saved': baseline_months - simulated_months,
                'total_interest': simulated_total_interest
            },
            'simulation': {
                'schedule': simulated_schedule,
                'total_interest': simulated_total_interest
            },
            'overpayments_list': db_overpayments
        }

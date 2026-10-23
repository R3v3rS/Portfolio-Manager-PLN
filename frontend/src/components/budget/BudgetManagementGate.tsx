import type { ReactNode } from 'react';
import { useBudgetMode } from './budgetMode';

export default function BudgetManagementGate({ children }: { children: ReactNode }) {
  const { management, setManagement } = useBudgetMode();
  return management ? <>{children}</> : <section className="budget-panel budget-mode-empty"><h2>Ustawienia budżetu</h2><p>Włącz zarządzanie, aby zmieniać kategorie, limity i zasady planowania.</p><button className="budget-button-secondary" onClick={() => setManagement(true)}>Włącz zarządzanie</button></section>;
}

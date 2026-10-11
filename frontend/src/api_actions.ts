import { createApiClient } from './apiConfig';

export type ActionCategory = 'investments' | 'budget' | 'loans' | 'other';
export interface DashboardAction {
  key: string;
  source: 'manual' | 'journal' | 'radar' | 'bill' | 'loan' | 'import' | 'goal' | 'budget_plan' | 'reserve' | 'bond';
  category: ActionCategory;
  title: string;
  description: string;
  due_date: string | null;
  href: string | null;
  action_label: string | null;
  amount: number | null;
  priority: 'normal' | 'high';
  timing?: 'overdue' | 'today' | 'upcoming' | 'unscheduled';
  task_id?: number;
  version?: number;
  completed_at?: string | null;
}
export interface ActionsWorkspace {
  as_of: string;
  horizon: string;
  items: DashboardAction[];
  completed: DashboardAction[];
  stats: { open: number; overdue: number; today: number; week: number; completed: number };
  warnings: string[];
}
export interface TaskPlan {
  title: string;
  notes: string;
  category: ActionCategory;
  due_date: string | null;
  priority: 'normal' | 'high';
}
const http = createApiClient('/dashboard');
export const actionsApi = {
  get: () => http.get<ActionsWorkspace>('/actions'),
  create: (plan: TaskPlan, request_id: string) => http.post<{ id: number }>('/tasks', { ...plan, request_id }),
  update: (id: number, plan: TaskPlan, version: number) => http.put<{ id: number }>(`/tasks/${id}`, { ...plan, version }),
  complete: (id: number, completed: boolean, version: number) => http.put<{ id: number }>(`/tasks/${id}/completion`, { completed, version }),
};

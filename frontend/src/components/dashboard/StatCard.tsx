import React from 'react';
import { Card } from './DashboardPrimitives';
import { cn } from '../../lib/utils';

const Sparkline: React.FC<{ positive?: boolean }> = ({ positive = true }) => (
  <svg viewBox="0 0 120 30" className="h-8 w-full opacity-85" fill="none">
    <path d="M2 24 L20 18 L34 19 L48 14 L64 16 L80 10 L96 12 L118 6" stroke={positive ? '#22c55e' : '#ef4444'} strokeWidth="2.2" />
  </svg>
);

export const StatCard: React.FC<{ label: string; value: string; tone?: 'neutral' | 'profit' | 'loss' }> = ({ label, value, tone = 'neutral' }) => (
  <Card className="rounded-3xl">
    <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
    <p className={cn('mt-3 text-3xl font-semibold tabular-nums', tone === 'profit' ? 'text-emerald-400' : tone === 'loss' ? 'text-red-400' : 'text-slate-100')}>
      {value}
    </p>
    <div className="mt-4">
      <Sparkline positive={tone !== 'loss'} />
    </div>
  </Card>
);

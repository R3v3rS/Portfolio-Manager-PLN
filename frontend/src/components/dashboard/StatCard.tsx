import React, { useEffect, useMemo, useState } from 'react';
import { Card } from './DashboardPrimitives';
import { cn } from '../../lib/utils';

const Sparkline: React.FC<{ positive?: boolean }> = ({ positive = true }) => (
  <svg viewBox="0 0 120 30" className="h-9 w-full opacity-90" fill="none">
    <defs>
      <linearGradient id={positive ? 'sparkProfit' : 'sparkLoss'} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={positive ? '#22c55e' : '#ef4444'} stopOpacity="0.35" />
        <stop offset="100%" stopColor={positive ? '#22c55e' : '#ef4444'} stopOpacity="0" />
      </linearGradient>
    </defs>
    <path d="M2 24 L20 18 L34 19 L48 14 L64 16 L80 10 L96 12 L118 6" stroke={positive ? '#22c55e' : '#ef4444'} strokeWidth="2.2" strokeLinecap="round" />
    <path d="M2 24 L20 18 L34 19 L48 14 L64 16 L80 10 L96 12 L118 6 L118 30 L2 30 Z" fill={positive ? 'url(#sparkProfit)' : 'url(#sparkLoss)'} />
  </svg>
);

export const StatCard: React.FC<{ label: string; value: string; tone?: 'neutral' | 'profit' | 'loss' }> = ({ label, value, tone = 'neutral' }) => {
  const parsedValue = useMemo(() => Number(value.replace(',', '.').replace(/[^\d.-]/g, '')) || 0, [value]);
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const duration = 700;
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      setAnimated(parsedValue * progress);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [parsedValue]);

  const suffix = value.replace(/[\d\s.,-]/g, '').trim();

  return (
    <Card className="rounded-3xl hover:scale-[1.01]">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p title={value} className={cn('mt-2 text-3xl font-semibold tabular-nums', tone === 'profit' ? 'text-[#22c55e]' : tone === 'loss' ? 'text-[#ef4444]' : 'text-slate-100')}>
        {animated.toLocaleString('pl-PL', { maximumFractionDigits: 2, minimumFractionDigits: suffix ? 2 : 0 })}
        {suffix ? ` ${suffix}` : ''}
      </p>
      <p className="mt-1 text-xs text-slate-500">Aktualizacja na żywo</p>
      <div className="mt-4">
        <Sparkline positive={tone !== 'loss'} />
      </div>
    </Card>
  );
};

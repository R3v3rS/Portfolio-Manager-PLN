import React from 'react';
import { cn } from '../../lib/utils';

type CardProps = React.PropsWithChildren<{ className?: string }>;

export const Card: React.FC<CardProps> = ({ className, children }) => (
  <div
    className={cn(
      'group relative overflow-hidden rounded-2xl border border-white/5 bg-[linear-gradient(145deg,#0f172a,#020617)] p-5 shadow-[0_8px_24px_rgba(0,0,0,0.25)] backdrop-blur-sm transition-all duration-200 ease-in-out hover:-translate-y-0.5 hover:shadow-[0_10px_30px_rgba(0,0,0,0.3)]',
      className,
    )}
  >
    <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.08),transparent_40%)] opacity-70" />
    <div className="relative z-10">{children}</div>
  </div>
);

export const SectionHeader: React.FC<{ title: string; subtitle?: string; rightSlot?: React.ReactNode }> = ({ title, subtitle, rightSlot }) => (
  <div className="mb-4 flex items-start justify-between gap-3">
    <div>
      <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
      {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
    </div>
    {rightSlot}
  </div>
);

export const Sidebar: React.FC<{ items: string[] }> = ({ items }) => (
  <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-white/5 bg-[#0B0F14]/95 p-4 lg:block">
    <div className="mb-6 rounded-xl border border-white/5 bg-slate-900/70 px-3 py-2 text-sm font-semibold text-slate-200">Portfolio Manager</div>
    <nav className="space-y-2">
      {items.map((item, idx) => (
        <button
          key={item}
          className={cn(
            'w-full rounded-xl px-3 py-2 text-left text-sm transition-all duration-200 ease-in-out active:scale-[0.99]',
            idx === 0
              ? 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/30'
              : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200',
          )}
        >
          {item}
        </button>
      ))}
    </nav>
  </aside>
);

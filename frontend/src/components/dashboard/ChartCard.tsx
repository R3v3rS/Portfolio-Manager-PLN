import React from 'react';
import { Card, SectionHeader } from './DashboardPrimitives';

export const RangeTabs: React.FC = () => (
  <div className="inline-flex rounded-xl border border-white/10 bg-slate-900/70 p-1">
    {['1D', '1M', '3M', 'YTD', 'ALL'].map((tab, index) => (
      <button
        key={tab}
        className={`rounded-lg px-3 py-1.5 text-xs transition-all duration-200 ease-in-out active:scale-95 ${index === 1 ? 'bg-gradient-to-r from-blue-500/25 to-violet-500/25 text-blue-200 ring-1 ring-blue-400/30' : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-200'}`}
      >
        {tab}
      </button>
    ))}
  </div>
);

export const ChartCard: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <Card className="hover:scale-[1.005]">
    <SectionHeader title={title} rightSlot={<RangeTabs />} />
    {children}
  </Card>
);

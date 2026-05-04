import React from 'react';
import { Card, SectionHeader } from './DashboardPrimitives';

export const RangeTabs: React.FC = () => (
  <div className="inline-flex rounded-xl border border-slate-700 bg-slate-900/60 p-1">
    {['1D', '1M', '3M', 'YTD', 'ALL'].map((tab, index) => (
      <button key={tab} className={`rounded-lg px-3 py-1.5 text-xs ${index === 1 ? 'bg-blue-500/20 text-blue-300' : 'text-slate-400 hover:text-slate-200'}`}>
        {tab}
      </button>
    ))}
  </div>
);

export const ChartCard: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <Card>
    <SectionHeader title={title} rightSlot={<RangeTabs />} />
    {children}
  </Card>
);

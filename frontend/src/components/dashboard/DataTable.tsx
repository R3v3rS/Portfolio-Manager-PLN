import React from 'react';
import { Holding } from '../../types';
import { cn } from '../../lib/utils';

const rowSpark = (negative: boolean) => (
  <svg viewBox="0 0 80 24" className="h-6 w-20" fill="none">
    <path d={negative ? 'M2 6 L16 10 L28 8 L42 14 L56 13 L78 19' : 'M2 19 L16 14 L28 16 L42 10 L56 12 L78 6'} stroke={negative ? '#ef4444' : '#22c55e'} strokeWidth="2" strokeLinecap="round" />
  </svg>
);

export const DataTable: React.FC<{ holdings: Holding[] }> = ({ holdings }) => (
  <div className="overflow-hidden rounded-2xl border border-white/5 bg-slate-950/35 p-3">
    <table className="min-w-full border-separate border-spacing-y-2 text-sm">
      <thead className="text-xs uppercase tracking-wide text-slate-500">
        <tr>
          <th className="px-4 py-2 text-left">Symbol</th><th className="px-4 py-2 text-right">Wartość</th><th className="px-4 py-2 text-right">PnL</th><th className="px-4 py-2 text-left">Sektor</th><th className="px-4 py-2 text-right">Trend</th>
        </tr>
      </thead>
      <tbody>
        {holdings.slice(0, 6).map((h) => {
          const pnl = h.profit_loss ?? 0;
          const negative = pnl < 0;
          return (
            <tr key={`${h.portfolio_id}-${h.ticker}`} className="rounded-xl border border-white/5 bg-slate-900/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] transition-all duration-200 ease-in-out hover:scale-[1.01] hover:bg-slate-800/90 hover:shadow-[0_0_0_1px_rgba(59,130,246,0.2),0_8px_24px_rgba(2,6,23,0.35)]">
              <td className="rounded-l-xl px-4 py-4 font-semibold text-slate-100">{h.ticker}</td>
              <td className="px-4 py-4 text-right tabular-nums text-slate-300">{(h.current_value ?? 0).toFixed(2)} PLN</td>
              <td title="Profit/Loss" className={cn('px-4 py-4 text-right font-semibold tabular-nums', pnl >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]')}>{pnl.toFixed(2)} PLN</td>
              <td className="px-4 py-4"><span className="rounded-full px-2.5 py-1 text-xs text-indigo-200 ring-1 ring-indigo-400/30 bg-indigo-500/15">{h.sector || 'N/A'}</span></td>
              <td className="rounded-r-xl px-4 py-4 text-right">{rowSpark(negative)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

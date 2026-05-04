import React from 'react';
import { Holding } from '../../types';
import { cn } from '../../lib/utils';

export const DataTable: React.FC<{ holdings: Holding[] }> = ({ holdings }) => (
  <div className="overflow-hidden rounded-2xl border border-slate-800">
    <table className="min-w-full text-sm">
      <thead className="bg-slate-900/90 text-xs uppercase tracking-wide text-slate-400">
        <tr>
          <th className="px-4 py-3 text-left">Symbol</th><th className="px-4 py-3 text-right">Wartość</th><th className="px-4 py-3 text-right">PnL</th><th className="px-4 py-3 text-left">Sektor</th>
        </tr>
      </thead>
      <tbody>
        {holdings.slice(0, 6).map((h) => {
          const pnl = h.profit_loss ?? 0;
          return (
            <tr key={`${h.portfolio_id}-${h.ticker}`} className="border-t border-slate-800 bg-slate-950/40 hover:bg-slate-900/80 transition-colors">
              <td className="px-4 py-3 font-medium text-slate-100">{h.ticker}</td>
              <td className="px-4 py-3 text-right tabular-nums text-slate-300">{(h.current_value ?? 0).toFixed(2)} PLN</td>
              <td className={cn('px-4 py-3 text-right font-semibold tabular-nums', pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>{pnl.toFixed(2)} PLN</td>
              <td className="px-4 py-3"><span className="rounded-full bg-indigo-500/15 px-2 py-1 text-xs text-indigo-300">{h.sector || 'N/A'}</span></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

export type StagingRowStatus = 'pending' | 'assigned' | 'booked' | 'rejected';

export type StagingConflictType =
  | 'missing_holding'
  | 'insufficient_qty'
  | 'database_duplicate'
  | 'file_internal_duplicate'
  | 'missing_symbol'
  | null;

export interface StagingRow {
  id: number;
  ticker: string;
  type: 'BUY' | 'SELL' | 'DEPOSIT' | 'WITHDRAW' | 'DIVIDEND' | 'INTEREST';
  quantity: number | null;
  price: number | null;
  total_value: number;
  date: string;
  status: StagingRowStatus;
  conflict_type: StagingConflictType;
  conflict_details: Record<string, unknown> | null;
  target_sub_portfolio_id: number | null;
  row_hash: string;
}

export interface StagingSession {
  session_id: string;
  portfolio_id: number;
  rows: StagingRow[];
  summary: {
    total: number;
    pending: number;
    conflicts: number;
    rejected: number;
    missing_symbols: string[];
  };
}

export interface BookResult {
  booked: number;
  booked_tx_only: number;
  skipped_conflicts: number;
  rejected: number;
  errors: string[];
}

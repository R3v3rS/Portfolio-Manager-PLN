export type StagingRowStatus = 'pending' | 'assigned' | 'booked' | 'rejected';

export type StagingConflictType =
  | 'missing_holding'
  | 'insufficient_qty'
  | 'database_duplicate'
  | 'file_internal_duplicate'
  | 'missing_symbol'
  | 'source_mismatch'
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
  commission?: number | null;
  source_operation_id?: string | null;
  source_row_number?: number | null;
  instrument_name?: string | null;
  booking_mode?: 'normal' | 'history_only' | 'duplicate_skipped' | 'cancelled' | null;
}

export interface StagingSession {
  session_id: string;
  portfolio_id: number;
  rows: StagingRow[];
  source_file?: string | null;
  created_at?: string;
  unsupported_rows?: { row_number: number; type: string; reason: string }[];
  warnings?: string[];
  summary: {
    total: number;
    pending: number;
    conflicts: number;
    rejected: number;
    missing_symbols: string[];
    input_rows?: number;
    booked?: number;
    unsupported?: number;
  };
}

export interface BookResult {
  booked: number;
  booked_tx_only: number;
  skipped_conflicts: number;
  rejected: number;
  errors: string[];
  duplicate_skipped?: number;
  remaining?: number;
  session?: StagingSession;
}

export interface ImportSessionListItem {
  session_id: string;
  source_file: string | null;
  created_at: string;
  summary: StagingSession['summary'];
}

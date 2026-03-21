export interface ApiSuccessEnvelope<TPayload> {
  payload: TPayload;
}

export interface ApiErrorBody<TDetails extends Record<string, unknown> = Record<string, unknown>> {
  message: string;
  code?: string;
  details?: TDetails;
}

export interface ApiErrorEnvelope<TDetails extends Record<string, unknown> = Record<string, unknown>> {
  error: ApiErrorBody<TDetails>;
}

export interface SymbolMappingDto {
  id: number;
  symbol_input: string;
  ticker: string;
  currency: 'PLN' | 'USD' | 'EUR' | 'GBP' | null;
  created_at: string | null;
}

export interface SymbolMappingDeleteDto {
  success: boolean;
  message: string;
}

export interface XtbImportErrorDetailsDto {
  missing_symbols?: string[];
}

export interface XtbImportSuccessDto {
  success: boolean;
  message: string;
  missing_symbols: string[];
}

export interface LoanMutationDto {
  id?: number;
  message: string;
}

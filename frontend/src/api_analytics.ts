import { ANALYTICS_ENDPOINTS, createApiClient } from './apiConfig';

const analyticsHttp = createApiClient('/analytics');

export interface MaxDrawdownMetric {
  value: number;
  start_date?: string;
  end_date?: string;
  recovery_date?: string | null;
  duration_days?: number;
}

export interface AnalyticsSummaryPayload {
  cached?: boolean;
  period?: string;
  performance?: {
    sharpe_ratio?: number | null;
    max_drawdown?: number | MaxDrawdownMetric | null;
    volatility_annualized?: number | null;
    total_return_pct?: number | null;
    best_day?: { date?: string; return?: number | null };
    worst_day?: { date?: string; return?: number | null };
  };
  risk?: {
    var_1d?: number | null;
    var_1d_percent?: number | null;
    var_1d_pct?: number | null;
    var_1d_pln?: number | null;
    cvar_1d_pct?: number | null;
    cvar_1d_pln?: number | null;
    data_points?: number | null;
    portfolio_value?: number | null;
    period_used?: string | null;
  };
  correlation?: {
    recharts_data?: Array<Record<string, string | number | null>>;
  };
  diversification?: {
    score?: number | null;
    rating?: string | null;
    recommendation?: string | null;
    top_concentration_warning?: string | null;
    by_sector?: Array<{
      sector?: string | null;
      value?: number | null;
      weight?: number | null;
      ticker?: string | null;
    }>;
  };
}

interface AnalyticsSummaryPayloadLegacy {
  performance_summary?: AnalyticsSummaryPayload['performance'];
  portfolio_var?: {
    var_1d_pct?: number | null;
    var_1d_percent?: number | null;
    var_1d?: number | null;
  } & AnalyticsSummaryPayload['risk'];
  correlation_risk?: AnalyticsSummaryPayload['correlation'];
}

type AnalyticsSummaryApiPayload = AnalyticsSummaryPayload & AnalyticsSummaryPayloadLegacy;

const normalizeSummaryPayload = (payload?: AnalyticsSummaryApiPayload): AnalyticsSummaryPayload => {
  if (!payload) return {};

  const performance = payload.performance ?? payload.performance_summary;
  const riskSource = payload.risk ?? payload.portfolio_var;
  const correlation = payload.correlation ?? payload.correlation_risk;

  return {
    ...payload,
    performance,
    risk: riskSource
      ? {
          ...riskSource,
          var_1d_percent: riskSource.var_1d_percent ?? riskSource.var_1d_pct ?? null,
        }
      : undefined,
    correlation: correlation
      ? {
          ...correlation,
          recharts_data: correlation.recharts_data ?? [],
        }
      : undefined,
  };
};

export const analyticsApi = {
  getSummary: async (portfolioId: number, subPortfolioId?: number, period = '1y'): Promise<AnalyticsSummaryPayload> => {
    const response = await analyticsHttp.get<AnalyticsSummaryApiPayload>(ANALYTICS_ENDPOINTS.summary, {
      params: {
        portfolio_id: portfolioId,
        sub_portfolio_id: subPortfolioId,
        period,
      },
    });

    return normalizeSummaryPayload(response);
  },
};

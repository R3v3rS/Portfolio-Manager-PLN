import { ANALYTICS_ENDPOINTS, createApiClient } from './apiConfig';

const analyticsHttp = createApiClient('/analytics');

interface ApiEnvelope<T> {
  payload?: T;
}

export interface MaxDrawdownMetric {
  value: number;
  start_date?: string;
  end_date?: string;
  recovery_date?: string | null;
  duration_days?: number;
}

export interface AnalyticsSummaryPayload {
  performance?: {
    sharpe_ratio?: number | null;
    max_drawdown?: number | MaxDrawdownMetric | null;
  };
  risk?: {
    var_1d?: number | null;
    var_1d_percent?: number | null;
    var_1d_pct?: number | null;
  };
  correlation?: {
    recharts_data?: Array<Record<string, string | number | null>>;
  };
  diversification?: {
    score?: number | null;
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
  getSummary: async (portfolioId: number, subPortfolioId?: number): Promise<AnalyticsSummaryPayload> => {
    const response = await analyticsHttp.get<ApiEnvelope<AnalyticsSummaryApiPayload>>(ANALYTICS_ENDPOINTS.summary, {
      params: {
        portfolio_id: portfolioId,
        sub_portfolio_id: subPortfolioId,
      },
    });

    return normalizeSummaryPayload(response?.payload);
  },
};

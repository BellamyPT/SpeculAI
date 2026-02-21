/**
 * API Client — typed fetch wrappers for all backend endpoints.
 *
 * All functions throw an Error with a descriptive message on non-2xx
 * responses so callers can display user-friendly error messages.
 *
 * Usage:
 *   import { fetchPortfolioSummary } from '@/api/client'
 *   const summary = await fetchPortfolioSummary()
 */

import type {
  PortfolioSummaryResponse,
  PortfolioPerformanceResponse,
  TradeResponse,
  DecisionReportResponse,
  DecisionReportDetailResponse,
  PaginatedResponse,
  PipelineStatusResponse,
  TradesQueryParams,
  DecisionsQueryParams,
  BacktestTriggerRequest,
  BacktestProgressResponse,
} from '@/types'

const BASE = '/api'

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    ...options,
  })

  if (!response.ok) {
    let message = `HTTP ${response.status}: ${response.statusText}`
    try {
      const body = await response.json()
      if (body?.error?.message) {
        message = body.error.message
      } else if (body?.detail) {
        message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      // Response body was not JSON — keep the HTTP status message
    }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

function buildQueryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ''
  )
  if (entries.length === 0) return ''
  const qs = entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&')
  return `?${qs}`
}

// ------------------------------------------------------------
// Portfolio
// ------------------------------------------------------------

/**
 * GET /api/portfolio/summary
 * Returns portfolio value, cash, positions with P&L.
 */
export async function fetchPortfolioSummary(): Promise<PortfolioSummaryResponse> {
  return apiFetch<PortfolioSummaryResponse>(`${BASE}/portfolio/summary`)
}

/**
 * GET /api/portfolio/performance
 * Returns time-series snapshots and benchmark comparison data.
 */
export async function fetchPortfolioPerformance(
  startDate?: string,
  endDate?: string
): Promise<PortfolioPerformanceResponse> {
  const qs = buildQueryString({ start_date: startDate, end_date: endDate })
  return apiFetch<PortfolioPerformanceResponse>(`${BASE}/portfolio/performance${qs}`)
}

// ------------------------------------------------------------
// Trades
// ------------------------------------------------------------

/**
 * GET /api/trades
 * Returns paginated trade history, filterable by ticker, side, status, and dates.
 */
export async function fetchTrades(
  params: TradesQueryParams = {}
): Promise<PaginatedResponse<TradeResponse>> {
  const qs = buildQueryString(params as Record<string, string | number | boolean | undefined | null>)
  return apiFetch<PaginatedResponse<TradeResponse>>(`${BASE}/trades${qs}`)
}

// ------------------------------------------------------------
// Decisions
// ------------------------------------------------------------

/**
 * GET /api/decisions
 * Returns paginated decision reports, filterable by ticker, action, confidence, and dates.
 */
export async function fetchDecisions(
  params: DecisionsQueryParams = {}
): Promise<PaginatedResponse<DecisionReportResponse>> {
  const qs = buildQueryString(params as Record<string, string | number | boolean | undefined | null>)
  return apiFetch<PaginatedResponse<DecisionReportResponse>>(`${BASE}/decisions${qs}`)
}

/**
 * GET /api/decisions/{id}
 * Returns full decision report with context items and outcome data.
 */
export async function fetchDecisionDetail(id: number): Promise<DecisionReportDetailResponse> {
  return apiFetch<DecisionReportDetailResponse>(`${BASE}/decisions/${id}`)
}

// ------------------------------------------------------------
// Pipeline
// ------------------------------------------------------------

/**
 * GET /api/pipeline/status
 * Returns the current pipeline status and last run metadata.
 */
export async function fetchPipelineStatus(): Promise<PipelineStatusResponse> {
  return apiFetch<PipelineStatusResponse>(`${BASE}/pipeline/status`)
}

/**
 * POST /api/pipeline/run
 * Triggers a manual pipeline run. Returns 202 Accepted immediately.
 */
export async function triggerPipeline(): Promise<{ message: string; pipeline_run_id: string }> {
  return apiFetch<{ message: string; pipeline_run_id: string }>(`${BASE}/pipeline/run`, {
    method: 'POST',
  })
}

// ------------------------------------------------------------
// Backtest
// ------------------------------------------------------------

/**
 * POST /api/backtest/run
 * Triggers a backtest run. Returns 202 Accepted with run ID.
 */
export async function triggerBacktest(
  params: BacktestTriggerRequest
): Promise<BacktestProgressResponse> {
  return apiFetch<BacktestProgressResponse>(`${BASE}/backtest/run`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/**
 * GET /api/backtest/{runId}
 * Returns backtest progress or final results.
 */
export async function fetchBacktestProgress(
  runId: string
): Promise<BacktestProgressResponse> {
  return apiFetch<BacktestProgressResponse>(`${BASE}/backtest/${runId}`)
}

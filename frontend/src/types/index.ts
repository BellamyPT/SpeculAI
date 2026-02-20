// ============================================================
// API Response Types — match backend Pydantic schemas exactly
// ============================================================

export interface PositionResponse {
  id: number
  stock_id: number
  ticker: string | null
  quantity: string
  avg_price: string
  current_price: string | null
  unrealized_pnl: string | null
  weight_pct: string | null
  currency: string
  opened_at: string
  closed_at: string | null
  status: string
}

export interface PortfolioSummaryResponse {
  total_value: string
  cash: string
  invested: string
  daily_pnl: string
  cumulative_pnl_pct: string
  num_positions: number
  positions: PositionResponse[]
}

export interface PortfolioSnapshotResponse {
  id: number
  date: string
  total_value: string
  cash: string
  invested: string
  daily_pnl: string
  cumulative_pnl_pct: string
  num_positions: number
  is_backtest: boolean
  backtest_run_id: string | null
}

export interface BenchmarkDataPoint {
  date: string
  value: number
}

export interface BenchmarkSeries {
  symbol: string
  name: string
  data: BenchmarkDataPoint[]
}

export interface PortfolioPerformanceResponse {
  snapshots: PortfolioSnapshotResponse[]
  benchmarks: BenchmarkSeries[]
}

export interface TradeResponse {
  id: number
  stock_id: number
  ticker: string | null
  decision_report_id: number | null
  side: string
  quantity: string
  price: string
  total_value: string
  currency: string
  broker_order_id: string | null
  status: string
  executed_at: string | null
  is_backtest: boolean
  created_at: string
}

export interface DecisionReportResponse {
  id: number
  stock_id: number
  ticker: string | null
  pipeline_run_id: string
  action: string
  confidence: string
  reasoning: string
  is_backtest: boolean
  created_at: string
}

export interface DecisionContextItemResponse {
  id: number
  decision_report_id: number
  context_type: string
  source: string
  content: string
  relevance_score: string | null
}

export interface DecisionReportDetailResponse extends DecisionReportResponse {
  technical_summary: Record<string, unknown>
  news_summary: Record<string, unknown>
  memory_references: Record<string, unknown> | null
  portfolio_state: Record<string, unknown>
  outcome_pnl: string | null
  outcome_benchmark_delta: string | null
  context_items: DecisionContextItemResponse[]
}

export interface PaginationMeta {
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: PaginationMeta
}

export interface PipelineLastRun {
  pipeline_run_id: string
  status: string
  started_at: string
  completed_at: string | null
  stocks_analyzed: number
  candidates_screened: number
  trades_approved: number
  trades_executed: number
  errors: string[]
}

export interface PipelineStatusResponse {
  status: string | null
  last_run: PipelineLastRun | null
}

// ============================================================
// Query Param Types
// ============================================================

export interface TradesQueryParams {
  ticker?: string
  side?: 'BUY' | 'SELL' | ''
  status?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export interface DecisionsQueryParams {
  ticker?: string
  action?: 'BUY' | 'SELL' | 'HOLD' | ''
  min_confidence?: number
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

// ============================================================
// UI-only Types
// ============================================================

export type SortDirection = 'asc' | 'desc'

export interface SortConfig<T extends string> {
  key: T
  direction: SortDirection
}

export type Action = 'BUY' | 'SELL' | 'HOLD'
export type TradeSide = 'BUY' | 'SELL'
export type PipelineStatus = 'RUNNING' | 'SUCCESS' | 'FAILED' | null

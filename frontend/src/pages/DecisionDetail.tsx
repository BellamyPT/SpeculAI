/**
 * DecisionDetail page — full detail view for a single decision report.
 *
 * Sections:
 * - Header: ticker, action badge, confidence bar, datetime
 * - Reasoning: full LLM reasoning text
 * - Technical indicators panel (from technical_summary JSONB)
 * - News context panel (from context_items filtered by type "news")
 * - Memory references panel (from context_items filtered by type "memory")
 * - Portfolio state at time of decision
 * - Outcome panel (if outcome has been assessed)
 */

import { useParams, Link } from 'react-router-dom'
import { useAsync } from '@/hooks/useAsync'
import { fetchDecisionDetail } from '@/api/client'
import { ActionBadge } from '@/components/ActionBadge'
import { ConfidenceBar } from '@/components/ConfidenceBar'
import { TechnicalIndicatorsPanel } from '@/components/TechnicalIndicatorsPanel'
import { NewsContextPanel } from '@/components/NewsContextPanel'
import { MemoryReferencesPanel } from '@/components/MemoryReferencesPanel'

function formatDatetime(value: string): string {
  return new Date(value).toLocaleString('en-GB', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatCurrency(value: string | null, currency = 'EUR'): string {
  if (!value) return '—'
  const n = parseFloat(value)
  if (isNaN(n)) return '—'
  return new Intl.NumberFormat('en-GB', {
    style: 'currency', currency,
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(n)
}

interface SectionCardProps {
  title: string
  children: React.ReactNode
  className?: string
  badge?: React.ReactNode
}

function SectionCard({ title, children, className = '', badge }: SectionCardProps) {
  return (
    <div className={`bg-gray-800 border border-gray-700 rounded-lg overflow-hidden ${className}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <h2 className="text-sm font-semibold text-gray-100">{title}</h2>
        {badge}
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}

export function DecisionDetail() {
  const { id } = useParams<{ id: string }>()
  const decisionId = id ? parseInt(id, 10) : NaN

  const { data, loading, error } = useAsync(
    () => {
      if (isNaN(decisionId)) return Promise.reject(new Error('Invalid decision ID'))
      return fetchDecisionDetail(decisionId)
    },
    [decisionId]
  )

  if (loading) {
    return (
      <main className="flex-1 overflow-y-auto p-6" aria-label="Loading decision detail">
        <div className="max-w-5xl mx-auto space-y-4">
          {/* Back link skeleton */}
          <div className="h-4 bg-gray-800 rounded w-24 animate-pulse" />
          {/* Header skeleton */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 animate-pulse space-y-4">
            <div className="flex gap-4">
              <div className="h-8 bg-gray-700 rounded w-20" />
              <div className="h-8 bg-gray-700 rounded w-16" />
            </div>
            <div className="h-3 bg-gray-700 rounded w-3/4" />
          </div>
          {/* Content skeletons */}
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-gray-800 border border-gray-700 rounded-lg h-32 animate-pulse" />
          ))}
        </div>
      </main>
    )
  }

  if (error || !data) {
    return (
      <main className="flex-1 overflow-y-auto p-6" aria-label="Decision detail error">
        <div className="max-w-5xl mx-auto">
          <Link
            to="/decisions"
            className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-white mb-4 group"
          >
            <span className="group-hover:-translate-x-0.5 transition-transform">←</span>
            Back to Decisions
          </Link>
          <div className="bg-loss/10 border border-loss/30 rounded-lg p-6 text-loss">
            <p className="font-semibold mb-1">Failed to load decision report</p>
            <p className="text-sm opacity-80">{error}</p>
          </div>
        </div>
      </main>
    )
  }

  const newsItems = data.context_items.filter((item) => item.context_type === 'news')
  const memoryItems = data.context_items.filter((item) => item.context_type === 'memory')
  const hasOutcome = data.outcome_pnl !== null || data.outcome_benchmark_delta !== null

  const portfolioState = data.portfolio_state as Record<string, string | number> | null

  return (
    <main className="flex-1 overflow-y-auto p-6" aria-label="Decision detail">
      <div className="max-w-5xl mx-auto space-y-5">

        {/* Back navigation */}
        <Link
          to="/decisions"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white group transition-colors"
          aria-label="Return to decisions list"
        >
          <span className="group-hover:-translate-x-0.5 transition-transform text-base">←</span>
          Back to Decisions
        </Link>

        {/* === HEADER === */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-5">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold font-mono text-white">
                {data.ticker ?? `Stock #${data.stock_id}`}
              </h1>
              <ActionBadge action={data.action} size="lg" />
              {data.is_backtest && (
                <span className="text-xs font-mono text-yellow-500 bg-yellow-500/10 border border-yellow-500/30 px-2 py-1 rounded">
                  BACKTEST
                </span>
              )}
            </div>
            <span className="text-xs font-mono text-gray-500 flex-shrink-0 mt-1">
              Report #{data.id}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wider block mb-1.5">
                Confidence
              </span>
              <ConfidenceBar value={data.confidence} showLabel />
            </div>
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wider block mb-1.5">
                Generated
              </span>
              <span className="text-sm text-gray-300">{formatDatetime(data.created_at)}</span>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-gray-700">
            <span className="text-xs text-gray-500">Pipeline run: </span>
            <span className="text-xs font-mono text-gray-400">{data.pipeline_run_id}</span>
          </div>
        </div>

        {/* === TWO-COLUMN LAYOUT (main content + sidebar) === */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">

          {/* Left column — main content */}
          <div className="xl:col-span-2 space-y-5">

            {/* Reasoning */}
            <SectionCard title="LLM Reasoning">
              <div
                className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap"
                role="article"
                aria-label="Decision reasoning"
              >
                {data.reasoning}
              </div>
            </SectionCard>

            {/* News context */}
            <SectionCard
              title="News Context"
              badge={
                <span className="text-xs text-gray-500 font-mono">
                  {newsItems.length} item{newsItems.length !== 1 ? 's' : ''}
                </span>
              }
            >
              <NewsContextPanel items={data.context_items} />
            </SectionCard>

            {/* Memory references */}
            <SectionCard
              title="Memory References"
              badge={
                <span className="text-xs text-gray-500 font-mono">
                  {memoryItems.length} item{memoryItems.length !== 1 ? 's' : ''}
                </span>
              }
            >
              <MemoryReferencesPanel items={data.context_items} />
            </SectionCard>
          </div>

          {/* Right column — sidebar panels */}
          <div className="space-y-5">

            {/* Technical indicators */}
            <SectionCard title="Technical Indicators">
              <TechnicalIndicatorsPanel data={data.technical_summary} />
            </SectionCard>

            {/* Portfolio state at decision time */}
            {portfolioState && Object.keys(portfolioState).length > 0 && (
              <SectionCard title="Portfolio State">
                <div className="space-y-0">
                  {Object.entries(portfolioState).map(([key, val]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between py-1.5 border-b border-gray-700/50 last:border-0"
                    >
                      <span className="text-xs text-gray-400 capitalize">
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs font-mono text-gray-200 tabular-nums">
                        {typeof val === 'number' ? val.toFixed(2) : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* Outcome assessment */}
            {hasOutcome && (
              <SectionCard title="Outcome Assessment">
                <div className="space-y-3">
                  {data.outcome_pnl !== null && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">Realized P&L</span>
                      <span
                        className={`text-sm font-mono font-semibold tabular-nums ${
                          parseFloat(data.outcome_pnl) >= 0 ? 'text-gain' : 'text-loss'
                        }`}
                      >
                        {formatCurrency(data.outcome_pnl)}
                      </span>
                    </div>
                  )}
                  {data.outcome_benchmark_delta !== null && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">vs Benchmark</span>
                      <span
                        className={`text-sm font-mono font-semibold tabular-nums ${
                          parseFloat(data.outcome_benchmark_delta) >= 0 ? 'text-gain' : 'text-loss'
                        }`}
                      >
                        {parseFloat(data.outcome_benchmark_delta) >= 0 ? '+' : ''}
                        {(parseFloat(data.outcome_benchmark_delta) * 100).toFixed(2)}%
                      </span>
                    </div>
                  )}
                </div>
              </SectionCard>
            )}

            {!hasOutcome && (
              <SectionCard title="Outcome Assessment">
                <p className="text-xs text-gray-500 italic text-center py-2">
                  Outcome not yet assessed.
                </p>
              </SectionCard>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}

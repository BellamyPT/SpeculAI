/**
 * PortfolioSummaryCard — displays key portfolio metrics in a card grid.
 *
 * Usage:
 *   <PortfolioSummaryCard data={portfolioSummary} loading={false} />
 */

import type { PortfolioSummaryResponse } from '@/types'

interface PortfolioSummaryCardProps {
  data: PortfolioSummaryResponse | null
  loading: boolean
  error: string | null
}

function formatCurrency(value: string | null | undefined, currency = 'EUR'): string {
  if (!value) return '—'
  const n = parseFloat(value)
  if (isNaN(n)) return '—'
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n)
}

function formatPct(value: string | null | undefined): string {
  if (!value) return '—'
  const n = parseFloat(value)
  if (isNaN(n)) return '—'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(2)}%`
}

function isPnlPositive(value: string | null | undefined): boolean {
  if (!value) return false
  return parseFloat(value) >= 0
}

interface MetricCardProps {
  label: string
  value: string
  isPositive?: boolean
  isNegative?: boolean
  subValue?: string
  loading?: boolean
}

function MetricCard({ label, value, isPositive, isNegative, subValue, loading }: MetricCardProps) {
  const valueColor = isPositive ? 'text-gain' : isNegative ? 'text-loss' : 'text-white'

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wider text-gray-400">{label}</span>
      {loading ? (
        <div className="h-7 bg-gray-700 rounded animate-pulse mt-1 w-3/4" />
      ) : (
        <span className={`text-2xl font-semibold font-mono tabular-nums ${valueColor}`}>
          {value}
        </span>
      )}
      {subValue && !loading && (
        <span className="text-xs text-gray-500 font-mono tabular-nums">{subValue}</span>
      )}
    </div>
  )
}

export function PortfolioSummaryCard({ data, loading, error }: PortfolioSummaryCardProps) {
  if (error) {
    return (
      <div className="bg-loss/10 border border-loss/30 rounded-lg p-4 text-loss text-sm">
        Failed to load portfolio summary: {error}
      </div>
    )
  }

  const pnlPositive = isPnlPositive(data?.daily_pnl)
  const cumPnlPositive = isPnlPositive(data?.cumulative_pnl_pct)

  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
      <MetricCard
        label="Total Portfolio Value"
        value={formatCurrency(data?.total_value)}
        loading={loading}
      />
      <MetricCard
        label="Cash Available"
        value={formatCurrency(data?.cash)}
        loading={loading}
        subValue={data ? `Invested: ${formatCurrency(data.invested)}` : undefined}
      />
      <MetricCard
        label="Daily P&L"
        value={formatCurrency(data?.daily_pnl)}
        loading={loading}
        isPositive={!loading && pnlPositive}
        isNegative={!loading && !pnlPositive && !!data?.daily_pnl}
      />
      <MetricCard
        label="Cumulative Return"
        value={formatPct(data?.cumulative_pnl_pct)}
        loading={loading}
        isPositive={!loading && cumPnlPositive}
        isNegative={!loading && !cumPnlPositive && !!data?.cumulative_pnl_pct}
        subValue={data ? `${data.num_positions} position${data.num_positions !== 1 ? 's' : ''}` : undefined}
      />
    </div>
  )
}

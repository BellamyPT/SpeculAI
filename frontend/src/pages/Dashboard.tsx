/**
 * Dashboard page — main overview with portfolio summary, performance chart,
 * and open positions table.
 *
 * Auto-refreshes all data on mount.
 */

import { useAsync } from '@/hooks/useAsync'
import { fetchPortfolioSummary, fetchPortfolioPerformance } from '@/api/client'
import { PortfolioSummaryCard } from '@/components/PortfolioSummaryCard'
import { PerformanceChart } from '@/components/PerformanceChart'
import { PositionsTable } from '@/components/PositionsTable'

export function Dashboard() {
  const summary = useAsync(() => fetchPortfolioSummary(), [])
  const performance = useAsync(() => fetchPortfolioPerformance(), [])

  const positions = summary.data?.positions ?? []

  return (
    <main className="flex-1 overflow-y-auto p-6 space-y-6" aria-label="Dashboard">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-400 mt-0.5">Portfolio overview and performance</p>
        </div>
        <button
          onClick={() => { summary.refetch(); performance.refetch() }}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition-colors"
          aria-label="Refresh dashboard data"
        >
          <span className="text-xs" aria-hidden="true">↻</span>
          Refresh
        </button>
      </div>

      {/* Portfolio metrics */}
      <section aria-label="Portfolio summary metrics">
        <PortfolioSummaryCard
          data={summary.data}
          loading={summary.loading}
          error={summary.error}
        />
      </section>

      {/* Performance chart */}
      <section aria-label="Portfolio performance chart">
        <PerformanceChart
          data={performance.data}
          loading={performance.loading}
          error={performance.error}
        />
      </section>

      {/* Positions table */}
      <section aria-label="Open positions">
        <PositionsTable
          positions={positions}
          loading={summary.loading}
        />
      </section>
    </main>
  )
}

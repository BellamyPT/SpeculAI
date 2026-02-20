/**
 * Trades page — paginated, filterable trade history.
 *
 * Filters: ticker (text), side (BUY/SELL), status, date range.
 * Each row links to the associated decision report if available.
 */

import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAsync } from '@/hooks/useAsync'
import { fetchTrades } from '@/api/client'
import { ActionBadge } from '@/components/ActionBadge'
import { FilterBar, type FilterField } from '@/components/FilterBar'
import { Pagination } from '@/components/Pagination'
import type { TradesQueryParams } from '@/types'

const LIMIT = 50

interface Filters {
  [key: string]: string | number
  ticker: string
  side: string
  status: string
  start_date: string
  end_date: string
}

const DEFAULT_FILTERS: Filters = {
  ticker: '',
  side: '',
  status: '',
  start_date: '',
  end_date: '',
}

const FILTER_FIELDS: FilterField[] = [
  { key: 'ticker', label: 'Ticker', type: 'text', placeholder: 'e.g. AAPL' },
  {
    key: 'side', label: 'Side', type: 'select', options: [
      { value: '', label: 'All sides' },
      { value: 'BUY', label: 'BUY' },
      { value: 'SELL', label: 'SELL' },
    ],
  },
  {
    key: 'status', label: 'Status', type: 'select', options: [
      { value: '', label: 'All statuses' },
      { value: 'EXECUTED', label: 'Executed' },
      { value: 'PENDING', label: 'Pending' },
      { value: 'FAILED', label: 'Failed' },
      { value: 'CANCELLED', label: 'Cancelled' },
    ],
  },
  { key: 'start_date', label: 'From', type: 'date' },
  { key: 'end_date', label: 'To', type: 'date' },
]

function formatCurrency(value: string, currency = 'EUR'): string {
  const n = parseFloat(value)
  if (isNaN(n)) return value
  return new Intl.NumberFormat('en-GB', {
    style: 'currency', currency,
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(n)
}

function formatDatetime(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function statusBadge(status: string) {
  const styles: Record<string, string> = {
    EXECUTED: 'text-gain bg-gain/10 border-gain/30',
    PENDING: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
    FAILED: 'text-loss bg-loss/10 border-loss/30',
    CANCELLED: 'text-gray-400 bg-gray-700 border-gray-600',
  }
  const style = styles[status.toUpperCase()] ?? styles.CANCELLED
  return (
    <span className={`text-xs font-mono px-1.5 py-0.5 rounded border ${style}`}>
      {status}
    </span>
  )
}

export function Trades() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [offset, setOffset] = useState(0)

  const queryParams: TradesQueryParams = {
    ...(filters.ticker ? { ticker: filters.ticker.toUpperCase() } : {}),
    ...(filters.side ? { side: filters.side as 'BUY' | 'SELL' } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    ...(filters.start_date ? { start_date: filters.start_date } : {}),
    ...(filters.end_date ? { end_date: filters.end_date } : {}),
    limit: LIMIT,
    offset,
  }

  const { data, loading, error, refetch } = useAsync(
    () => fetchTrades(queryParams),
    [filters, offset]
  )

  const handleFilterChange = useCallback((key: string, value: string | number) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setOffset(0)
  }, [])

  const handleReset = useCallback(() => {
    setFilters(DEFAULT_FILTERS)
    setOffset(0)
  }, [])

  const trades = data?.data ?? []
  const pagination = data?.pagination

  return (
    <main className="flex-1 overflow-y-auto p-6 space-y-5" aria-label="Trades">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Trades</h1>
          <p className="text-sm text-gray-400 mt-0.5">Full trade execution history</p>
        </div>
        <button
          onClick={refetch}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition-colors"
          aria-label="Refresh trades"
        >
          <span className="text-xs">↻</span>
          Refresh
        </button>
      </div>

      {/* Filters */}
      <FilterBar
        fields={FILTER_FIELDS}
        values={filters}
        onChange={handleFilterChange}
        onReset={handleReset}
      />

      {/* Error */}
      {error && (
        <div className="bg-loss/10 border border-loss/30 rounded-lg p-4 text-loss text-sm">
          Failed to load trades: {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]" role="table">
            <thead className="bg-gray-900/60 border-b border-gray-700">
              <tr>
                {['ID', 'Ticker', 'Side', 'Quantity', 'Price', 'Total Value', 'Status', 'Executed At', 'Decision'].map(
                  (col) => (
                    <th
                      key={col}
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider whitespace-nowrap"
                    >
                      {col}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {loading &&
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-gray-700 rounded w-20" />
                      </td>
                    ))}
                  </tr>
                ))}

              {!loading && trades.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-sm text-gray-500 italic">
                    No trades found matching the current filters.
                  </td>
                </tr>
              )}

              {!loading &&
                trades.map((trade) => (
                  <tr key={trade.id} className="hover:bg-gray-700/40 transition-colors">
                    <td className="px-4 py-3 text-xs font-mono text-gray-500">#{trade.id}</td>
                    <td className="px-4 py-3">
                      <span className="text-sm font-semibold font-mono text-white">
                        {trade.ticker ?? `#${trade.stock_id}`}
                      </span>
                      {trade.is_backtest && (
                        <span className="ml-1.5 text-xs text-gray-500 font-mono">[BT]</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ActionBadge action={trade.side} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-gray-300 tabular-nums">
                      {parseFloat(trade.quantity).toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-gray-300 tabular-nums">
                      {formatCurrency(trade.price, trade.currency)}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-gray-100 tabular-nums font-medium">
                      {formatCurrency(trade.total_value, trade.currency)}
                    </td>
                    <td className="px-4 py-3">{statusBadge(trade.status)}</td>
                    <td className="px-4 py-3 text-xs font-mono text-gray-400">
                      {formatDatetime(trade.executed_at)}
                    </td>
                    <td className="px-4 py-3">
                      {trade.decision_report_id ? (
                        <Link
                          to={`/decisions/${trade.decision_report_id}`}
                          className="text-xs text-blue-400 hover:text-blue-300 hover:underline font-mono"
                        >
                          View #{trade.decision_report_id}
                        </Link>
                      ) : (
                        <span className="text-xs text-gray-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pagination && (
          <div className="px-4 py-3 border-t border-gray-700">
            <Pagination
              total={pagination.total}
              limit={pagination.limit}
              offset={pagination.offset}
              onOffsetChange={setOffset}
            />
          </div>
        )}
      </div>
    </main>
  )
}

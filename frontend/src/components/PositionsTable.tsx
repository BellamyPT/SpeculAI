/**
 * PositionsTable — sortable table of current portfolio positions.
 *
 * Columns: ticker, quantity, avg price, current price, unrealized P&L, weight %
 * Rows are colorized by P&L direction.
 *
 * Usage:
 *   <PositionsTable positions={portfolioSummary.positions} loading={false} />
 */

import { useState } from 'react'
import type { PositionResponse, SortConfig } from '@/types'

interface PositionsTableProps {
  positions: PositionResponse[]
  loading: boolean
}

type SortKey = 'ticker' | 'quantity' | 'avg_price' | 'current_price' | 'unrealized_pnl' | 'weight_pct'

function formatNum(value: string | null | undefined, decimals = 2): string {
  if (!value) return '—'
  const n = parseFloat(value)
  return isNaN(n) ? '—' : n.toFixed(decimals)
}

function formatCurrency(value: string | null | undefined): string {
  if (!value) return '—'
  const n = parseFloat(value)
  if (isNaN(n)) return '—'
  return new Intl.NumberFormat('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
}

function pnlColor(value: string | null | undefined): string {
  if (!value) return 'text-gray-400'
  const n = parseFloat(value)
  if (isNaN(n)) return 'text-gray-400'
  return n >= 0 ? 'text-gain' : 'text-loss'
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    OPEN: 'bg-gain/20 text-gain border-gain/40',
    CLOSED: 'bg-gray-700 text-gray-400 border-gray-600',
    PARTIAL: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
  }
  const style = colors[status.toUpperCase()] ?? colors.CLOSED
  return (
    <span className={`text-xs font-mono px-1.5 py-0.5 rounded border ${style}`}>
      {status}
    </span>
  )
}

function SortIndicator({ active, direction }: { active: boolean; direction: 'asc' | 'desc' }) {
  if (!active) return <span className="text-gray-600 text-xs ml-1">&#8597;</span>
  return <span className="text-blue-400 text-xs ml-1">{direction === 'asc' ? '↑' : '↓'}</span>
}

function sortPositions(positions: PositionResponse[], sort: SortConfig<SortKey>): PositionResponse[] {
  return [...positions].sort((a, b) => {
    let aVal: string | number = a[sort.key] ?? ''
    let bVal: string | number = b[sort.key] ?? ''

    // Numeric fields
    const numericKeys: SortKey[] = ['quantity', 'avg_price', 'current_price', 'unrealized_pnl', 'weight_pct']
    if (numericKeys.includes(sort.key)) {
      aVal = parseFloat(String(aVal)) || 0
      bVal = parseFloat(String(bVal)) || 0
    }

    if (aVal < bVal) return sort.direction === 'asc' ? -1 : 1
    if (aVal > bVal) return sort.direction === 'asc' ? 1 : -1
    return 0
  })
}

export function PositionsTable({ positions, loading }: PositionsTableProps) {
  const [sort, setSort] = useState<SortConfig<SortKey>>({ key: 'weight_pct', direction: 'desc' })

  const handleSort = (key: SortKey) => {
    setSort((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
    }))
  }

  const sorted = sortPositions(positions, sort)

  const HeaderCell = ({ label, sortKey }: { label: string; sortKey: SortKey }) => (
    <th
      scope="col"
      className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer select-none hover:text-gray-200 transition-colors whitespace-nowrap"
      onClick={() => handleSort(sortKey)}
      aria-sort={sort.key === sortKey ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      {label}
      <SortIndicator active={sort.key === sortKey} direction={sort.direction} />
    </th>
  )

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm font-semibold text-gray-100">
          Open Positions
          {!loading && (
            <span className="ml-2 text-xs font-normal text-gray-400">
              ({positions.length})
            </span>
          )}
        </h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px]" role="table">
          <thead className="bg-gray-900/60">
            <tr>
              <HeaderCell label="Ticker" sortKey="ticker" />
              <HeaderCell label="Qty" sortKey="quantity" />
              <HeaderCell label="Avg Price" sortKey="avg_price" />
              <HeaderCell label="Current Price" sortKey="current_price" />
              <HeaderCell label="Unrealized P&L" sortKey="unrealized_pnl" />
              <HeaderCell label="Weight" sortKey="weight_pct" />
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Currency
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {loading && (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 bg-gray-700 rounded w-20" />
                    </td>
                  ))}
                </tr>
              ))
            )}
            {!loading && sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-sm text-gray-500 italic">
                  No open positions found.
                </td>
              </tr>
            )}
            {!loading && sorted.map((pos) => {
              const pnl = parseFloat(pos.unrealized_pnl ?? '0')
              const pnlSign = pnl >= 0 ? '+' : ''

              return (
                <tr
                  key={pos.id}
                  className="hover:bg-gray-700/40 transition-colors"
                >
                  <td className="px-4 py-3">
                    <span className="text-sm font-semibold font-mono text-white">
                      {pos.ticker ?? `#${pos.stock_id}`}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-300 tabular-nums">
                    {formatNum(pos.quantity, 4)}
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-300 tabular-nums">
                    {formatCurrency(pos.avg_price)}
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-100 tabular-nums">
                    {formatCurrency(pos.current_price)}
                  </td>
                  <td className={`px-4 py-3 text-sm font-mono tabular-nums font-medium ${pnlColor(pos.unrealized_pnl)}`}>
                    {pos.unrealized_pnl
                      ? `${pnlSign}${formatCurrency(pos.unrealized_pnl)}`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-gray-300 tabular-nums">
                    {pos.weight_pct ? `${parseFloat(pos.weight_pct).toFixed(1)}%` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {statusBadge(pos.status)}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 font-mono">
                    {pos.currency}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * Decisions page — paginated, filterable decision report cards.
 *
 * Filters: ticker, action (BUY/SELL/HOLD), min confidence, date range.
 * Each card is clickable and navigates to the full decision detail view.
 */

import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAsync } from '@/hooks/useAsync'
import { fetchDecisions } from '@/api/client'
import { ActionBadge } from '@/components/ActionBadge'
import { ConfidenceBar } from '@/components/ConfidenceBar'
import { FilterBar, type FilterField } from '@/components/FilterBar'
import { Pagination } from '@/components/Pagination'
import type { DecisionsQueryParams } from '@/types'

const LIMIT = 24

interface Filters {
  [key: string]: string | number
  ticker: string
  action: string
  min_confidence: number | ''
  start_date: string
  end_date: string
}

const DEFAULT_FILTERS: Filters = {
  ticker: '',
  action: '',
  min_confidence: '',
  start_date: '',
  end_date: '',
}

const FILTER_FIELDS: FilterField[] = [
  { key: 'ticker', label: 'Ticker', type: 'text', placeholder: 'e.g. AAPL' },
  {
    key: 'action', label: 'Action', type: 'select', options: [
      { value: '', label: 'All actions' },
      { value: 'BUY', label: 'BUY' },
      { value: 'SELL', label: 'SELL' },
      { value: 'HOLD', label: 'HOLD' },
    ],
  },
  {
    key: 'min_confidence',
    label: 'Min Confidence',
    type: 'number',
    placeholder: '0.0 – 1.0',
    min: 0,
    max: 1,
    step: 0.05,
  },
  { key: 'start_date', label: 'From', type: 'date' },
  { key: 'end_date', label: 'To', type: 'date' },
]

function formatDatetime(value: string): string {
  return new Date(value).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function truncate(text: string, maxLen = 160): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen).trimEnd() + '…'
}

export function Decisions() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [offset, setOffset] = useState(0)

  const queryParams: DecisionsQueryParams = {
    ...(filters.ticker ? { ticker: filters.ticker.toUpperCase() } : {}),
    ...(filters.action ? { action: filters.action as 'BUY' | 'SELL' | 'HOLD' } : {}),
    ...(filters.min_confidence !== '' ? { min_confidence: Number(filters.min_confidence) } : {}),
    ...(filters.start_date ? { start_date: filters.start_date } : {}),
    ...(filters.end_date ? { end_date: filters.end_date } : {}),
    limit: LIMIT,
    offset,
  }

  const { data, loading, error, refetch } = useAsync(
    () => fetchDecisions(queryParams),
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

  const decisions = data?.data ?? []
  const pagination = data?.pagination

  return (
    <main className="flex-1 overflow-y-auto p-6 space-y-5" aria-label="Decisions">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Decisions</h1>
          <p className="text-sm text-gray-400 mt-0.5">LLM-generated trade recommendations</p>
        </div>
        <button
          onClick={refetch}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition-colors"
          aria-label="Refresh decisions"
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
          Failed to load decisions: {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-gray-800 border border-gray-700 rounded-lg p-4 animate-pulse space-y-3">
              <div className="flex gap-2">
                <div className="h-6 bg-gray-700 rounded w-16" />
                <div className="h-6 bg-gray-700 rounded w-12" />
              </div>
              <div className="h-2 bg-gray-700 rounded w-full" />
              <div className="h-4 bg-gray-700 rounded w-3/4" />
              <div className="h-4 bg-gray-700 rounded w-1/2" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && decisions.length === 0 && !error && (
        <div className="flex items-center justify-center py-16">
          <p className="text-gray-500 italic text-sm">No decisions found matching the current filters.</p>
        </div>
      )}

      {/* Decision cards */}
      {!loading && decisions.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {decisions.map((decision) => (
            <Link
              key={decision.id}
              to={`/decisions/${decision.id}`}
              className="block group bg-gray-800 border border-gray-700 rounded-lg p-4 hover:border-gray-500 hover:bg-gray-750 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900"
              aria-label={`Decision ${decision.id}: ${decision.action} ${decision.ticker ?? `stock #${decision.stock_id}`}`}
            >
              {/* Card header */}
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-base font-bold font-mono text-white truncate">
                    {decision.ticker ?? `#${decision.stock_id}`}
                  </span>
                  <ActionBadge action={decision.action} />
                  {decision.is_backtest && (
                    <span className="text-xs text-gray-500 font-mono flex-shrink-0">[BT]</span>
                  )}
                </div>
                <span className="text-xs text-gray-500 font-mono flex-shrink-0">
                  #{decision.id}
                </span>
              </div>

              {/* Confidence bar */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-500">Confidence</span>
                </div>
                <ConfidenceBar value={decision.confidence} showLabel />
              </div>

              {/* Reasoning snippet */}
              <p className="text-sm text-gray-400 leading-relaxed group-hover:text-gray-300 transition-colors line-clamp-3">
                {truncate(decision.reasoning)}
              </p>

              {/* Footer */}
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-700">
                <span className="text-xs text-gray-500 font-mono">
                  {formatDatetime(decision.created_at)}
                </span>
                <span className="text-xs text-blue-400 group-hover:text-blue-300 font-medium">
                  View report →
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {pagination && !loading && (
        <Pagination
          total={pagination.total}
          limit={pagination.limit}
          offset={pagination.offset}
          onOffsetChange={setOffset}
        />
      )}
    </main>
  )
}

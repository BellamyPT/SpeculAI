/**
 * Backtest page — run historical backtests and view results.
 *
 * Sections:
 *   1. Configuration form (date range, initial capital)
 *   2. Progress indicator (while running)
 *   3. Results: metrics cards + equity curve chart
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { triggerBacktest, fetchBacktestProgress } from '@/api/client'
import type { BacktestProgressResponse } from '@/types'
import { createChart, type IChartApi, type ISeriesApi, type LineData, type Time } from 'lightweight-charts'

// ── Metric Card ──────────────────────────────────────────────

function MetricCard({
  label,
  value,
  suffix = '',
  positive,
}: {
  label: string
  value: string | number
  suffix?: string
  positive?: boolean | null
}) {
  let color = 'text-gray-100'
  if (positive === true) color = 'text-gain'
  if (positive === false) color = 'text-loss'

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <p className="text-xs text-gray-400 uppercase tracking-wider">{label}</p>
      <p className={`text-lg font-bold mt-1 font-mono ${color}`}>
        {value}{suffix}
      </p>
    </div>
  )
}

// ── Equity Chart ─────────────────────────────────────────────

function EquityChart({ data }: { data: { date: string; value: number }[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    if (!chartRef.current) {
      chartRef.current = createChart(containerRef.current, {
        layout: {
          background: { color: '#1f2937' },
          textColor: '#9ca3af',
        },
        grid: {
          vertLines: { color: '#374151' },
          horzLines: { color: '#374151' },
        },
        width: containerRef.current.clientWidth,
        height: 350,
        timeScale: { borderColor: '#4b5563' },
        rightPriceScale: { borderColor: '#4b5563' },
      })

      seriesRef.current = chartRef.current.addLineSeries({
        color: '#3b82f6',
        lineWidth: 2,
      })
    }

    const lineData: LineData[] = data.map((p) => ({
      time: p.date as Time,
      value: p.value,
    }))

    seriesRef.current?.setData(lineData)
    chartRef.current?.timeScale().fitContent()

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [data])

  useEffect(() => {
    return () => {
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
        seriesRef.current = null
      }
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden border border-gray-700"
    />
  )
}

// ── Progress Bar ─────────────────────────────────────────────

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0
  return (
    <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
      <div
        className="bg-blue-500 h-full rounded-full transition-all duration-300"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────

export function Backtest() {
  // Form state
  const today = new Date().toISOString().slice(0, 10)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [initialCapital, setInitialCapital] = useState(50000)
  const [formError, setFormError] = useState<string | null>(null)

  // Run state
  const [progress, setProgress] = useState<BacktestProgressResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const isRunning = progress?.status === 'RUNNING' || progress?.status === 'PENDING'
  const isComplete = progress?.status === 'COMPLETED'
  const isFailed = progress?.status === 'FAILED'

  // ── Polling ───────────────────────────────────────────────

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (id: string) => {
      stopPolling()
      pollRef.current = setInterval(async () => {
        try {
          const result = await fetchBacktestProgress(id)
          setProgress(result)
          if (result.status !== 'RUNNING' && result.status !== 'PENDING') {
            stopPolling()
          }
        } catch {
          // Keep polling on transient errors
        }
      }, 3000)
    },
    [stopPolling]
  )

  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  // ── Form validation & submit ──────────────────────────────

  function validate(): boolean {
    if (!startDate || !endDate) {
      setFormError('Please select both start and end dates')
      return false
    }
    if (startDate >= endDate) {
      setFormError('Start date must be before end date')
      return false
    }
    if (endDate > today) {
      setFormError('End date cannot be in the future')
      return false
    }
    const msRange = new Date(endDate).getTime() - new Date(startDate).getTime()
    const yearRange = msRange / (1000 * 60 * 60 * 24 * 365)
    if (yearRange > 5) {
      setFormError('Date range cannot exceed 5 years')
      return false
    }
    if (initialCapital <= 0) {
      setFormError('Initial capital must be positive')
      return false
    }
    setFormError(null)
    return true
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    setError(null)
    setProgress(null)

    try {
      const result = await triggerBacktest({
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
      })
      setProgress(result)
      startPolling(result.backtest_run_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start backtest')
    } finally {
      setLoading(false)
    }
  }

  const metrics = progress?.metrics

  return (
    <main className="flex-1 overflow-y-auto p-6 space-y-6" aria-label="Backtest">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white">Backtest</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          Test strategy performance against historical data
        </p>
      </div>

      {/* Configuration Form */}
      <form
        onSubmit={handleSubmit}
        className="bg-gray-800 rounded-lg border border-gray-700 p-5 space-y-4"
      >
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={today}
              className="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-md text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              max={today}
              className="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-md text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Initial Capital</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              min={1}
              step={1000}
              className="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-md text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {formError && <p className="text-xs text-loss">{formError}</p>}
        {error && <p className="text-xs text-loss">{error}</p>}

        <button
          type="submit"
          disabled={loading || isRunning}
          className="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white transition-colors"
        >
          {loading ? 'Starting...' : isRunning ? 'Backtest running...' : 'Run Backtest'}
        </button>
      </form>

      {/* Progress Section */}
      {isRunning && progress && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-300">
              Processing day {progress.current_day} of {progress.total_days}...
            </p>
            <span className="text-xs text-gray-500">
              {progress.total_days > 0
                ? Math.round((progress.current_day / progress.total_days) * 100)
                : 0}%
            </span>
          </div>
          <ProgressBar current={progress.current_day} total={progress.total_days} />
        </div>
      )}

      {/* Error Section */}
      {isFailed && progress && (
        <div className="bg-loss/10 border border-loss/30 rounded-lg p-4">
          <p className="text-sm font-medium text-loss">Backtest Failed</p>
          {progress.errors.length > 0 && (
            <ul className="mt-2 text-xs text-gray-400 space-y-1">
              {progress.errors.slice(0, 5).map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Results Section */}
      {isComplete && metrics && (
        <>
          {/* Metrics Cards */}
          <section aria-label="Backtest metrics">
            <h2 className="text-sm font-semibold text-gray-300 mb-3">Performance Metrics</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <MetricCard
                label="Total Return"
                value={metrics.total_return_pct.toFixed(2)}
                suffix="%"
                positive={metrics.total_return_pct > 0 ? true : metrics.total_return_pct < 0 ? false : null}
              />
              <MetricCard
                label="Annualized Return"
                value={metrics.annualized_return_pct.toFixed(2)}
                suffix="%"
                positive={metrics.annualized_return_pct > 0 ? true : metrics.annualized_return_pct < 0 ? false : null}
              />
              <MetricCard
                label="Max Drawdown"
                value={metrics.max_drawdown_pct.toFixed(2)}
                suffix="%"
                positive={metrics.max_drawdown_pct === 0 ? null : false}
              />
              <MetricCard
                label="Sharpe Ratio"
                value={metrics.sharpe_ratio.toFixed(2)}
                positive={metrics.sharpe_ratio > 1 ? true : metrics.sharpe_ratio < 0 ? false : null}
              />
              <MetricCard
                label="Win Rate"
                value={metrics.win_rate_pct.toFixed(1)}
                suffix="%"
                positive={metrics.win_rate_pct >= 50 ? true : metrics.win_rate_pct > 0 ? false : null}
              />
              <MetricCard
                label="Total Trades"
                value={metrics.total_trades}
              />
              <MetricCard
                label="Avg Holding Days"
                value={metrics.avg_holding_days.toFixed(1)}
              />
            </div>
          </section>

          {/* Equity Curve */}
          {progress?.equity_curve && progress.equity_curve.length > 0 && (
            <section aria-label="Equity curve chart">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">Equity Curve</h2>
              <EquityChart data={progress.equity_curve} />
            </section>
          )}

          {/* Errors during run */}
          {progress && progress.errors.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-300 mb-2">Warnings</h2>
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-3">
                <ul className="text-xs text-gray-400 space-y-1 max-h-40 overflow-y-auto">
                  {progress.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            </section>
          )}
        </>
      )}
    </main>
  )
}

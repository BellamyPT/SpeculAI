/**
 * PerformanceChart — TradingView Lightweight Charts line chart for portfolio
 * performance with toggleable benchmark overlays.
 *
 * Usage:
 *   <PerformanceChart data={portfolioPerformance} loading={false} />
 */

import { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, LineStyle, type IChartApi, type ISeriesApi, type LineData } from 'lightweight-charts'
import type { PortfolioPerformanceResponse } from '@/types'

interface PerformanceChartProps {
  data: PortfolioPerformanceResponse | null
  loading: boolean
  error: string | null
}

const CHART_COLORS = {
  portfolio: '#3b82f6',    // blue-500
  benchmarks: ['#a855f7', '#f59e0b', '#06b6d4', '#ec4899'],  // purple, amber, cyan, pink
  background: '#1f2937',   // gray-800
  grid: '#374151',         // gray-700
  text: '#9ca3af',         // gray-400
  crosshair: '#6b7280',    // gray-500
}

type BenchmarkToggle = Record<string, boolean>

export function PerformanceChart({ data, loading, error }: PerformanceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map())
  const [benchmarkToggles, setBenchmarkToggles] = useState<BenchmarkToggle>({})

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART_COLORS.background },
        textColor: CHART_COLORS.text,
        fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: CHART_COLORS.grid, style: LineStyle.Dotted },
        horzLines: { color: CHART_COLORS.grid, style: LineStyle.Dotted },
      },
      crosshair: {
        vertLine: { color: CHART_COLORS.crosshair, width: 1, style: LineStyle.Dashed },
        horzLine: { color: CHART_COLORS.crosshair, width: 1, style: LineStyle.Dashed },
      },
      rightPriceScale: {
        borderColor: CHART_COLORS.grid,
        textColor: CHART_COLORS.text,
      },
      timeScale: {
        borderColor: CHART_COLORS.grid,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    })

    chartRef.current = chart

    // Resize observer for responsive layout
    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    })
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current.clear()
    }
  }, [])

  // Populate data when it arrives
  useEffect(() => {
    if (!chartRef.current || !data) return

    const chart = chartRef.current
    seriesRef.current.forEach((s) => chart.removeSeries(s))
    seriesRef.current.clear()

    // Portfolio series
    if (data.snapshots.length > 0) {
      const portfolioSeries = chart.addLineSeries({
        color: CHART_COLORS.portfolio,
        lineWidth: 2,
        title: 'Portfolio',
        priceLineVisible: true,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
      })

      const portfolioData: LineData[] = data.snapshots
        .map((s) => ({
          time: s.date as LineData['time'],
          value: parseFloat(s.total_value),
        }))
        .filter((d) => !isNaN(d.value))
        .sort((a, b) => String(a.time).localeCompare(String(b.time)))

      portfolioSeries.setData(portfolioData)
      seriesRef.current.set('portfolio', portfolioSeries)
    }

    // Benchmark series
    const initialToggles: BenchmarkToggle = {}
    data.benchmarks.forEach((bm, idx) => {
      initialToggles[bm.symbol] = true

      const color = CHART_COLORS.benchmarks[idx % CHART_COLORS.benchmarks.length]
      const bmSeries = chart.addLineSeries({
        color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        title: bm.symbol,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 3,
      })

      const bmData: LineData[] = bm.data
        .map((d) => ({ time: d.date as LineData['time'], value: d.value }))
        .filter((d) => !isNaN(d.value))
        .sort((a, b) => String(a.time).localeCompare(String(b.time)))

      bmSeries.setData(bmData)
      seriesRef.current.set(bm.symbol, bmSeries)
    })

    setBenchmarkToggles(initialToggles)
    chart.timeScale().fitContent()
  }, [data])

  // Handle benchmark toggle visibility
  const toggleBenchmark = (symbol: string) => {
    setBenchmarkToggles((prev) => {
      const next = { ...prev, [symbol]: !prev[symbol] }
      const series = seriesRef.current.get(symbol)
      if (series) {
        series.applyOptions({ visible: next[symbol] })
      }
      return next
    })
  }

  if (error) {
    return (
      <div className="bg-loss/10 border border-loss/30 rounded-lg p-4 text-loss text-sm">
        Failed to load performance data: {error}
      </div>
    )
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      {/* Header with benchmark toggles */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm font-semibold text-gray-100">Portfolio Performance</h3>

        <div className="flex items-center gap-2">
          {/* Portfolio legend */}
          <button
            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/40"
            aria-label="Portfolio series (always visible)"
            disabled
          >
            <span className="w-3 h-0.5 bg-blue-500 rounded inline-block" />
            Portfolio
          </button>

          {/* Benchmark toggles */}
          {data?.benchmarks.map((bm, idx) => {
            const color = CHART_COLORS.benchmarks[idx % CHART_COLORS.benchmarks.length]
            const active = benchmarkToggles[bm.symbol] !== false
            return (
              <button
                key={bm.symbol}
                onClick={() => toggleBenchmark(bm.symbol)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium border transition-all ${
                  active
                    ? 'text-gray-200 border-gray-600 bg-gray-700/60'
                    : 'text-gray-500 border-gray-700 bg-transparent opacity-50'
                }`}
                aria-pressed={active}
                aria-label={`Toggle ${bm.name} benchmark`}
                title={bm.name}
              >
                <span
                  className="w-3 h-0.5 rounded inline-block"
                  style={{ backgroundColor: color, borderTop: `2px dashed ${color}`, height: '1px' }}
                />
                {bm.symbol}
              </button>
            )
          })}
        </div>
      </div>

      {/* Chart container */}
      <div className="relative" style={{ height: '360px' }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-800 z-10">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-400">Loading chart data...</span>
            </div>
          </div>
        )}
        {!loading && data && data.snapshots.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-sm text-gray-500 italic">No performance data available yet.</span>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" aria-label="Portfolio performance chart" />
      </div>
    </div>
  )
}

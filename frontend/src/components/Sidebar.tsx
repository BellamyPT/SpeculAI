/**
 * Sidebar — main navigation sidebar with pipeline status badge.
 *
 * Displays nav links with active state highlighting.
 * Polls pipeline status every 15 seconds to show current run state.
 *
 * Usage:
 *   <Sidebar />
 */

import { useEffect, useState, useCallback } from 'react'
import { NavLink } from 'react-router-dom'
import { fetchPipelineStatus, triggerPipeline } from '@/api/client'
import type { PipelineStatusResponse } from '@/types'

interface NavItem {
  to: string
  label: string
  icon: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: '◈' },
  { to: '/trades', label: 'Trades', icon: '⇄' },
  { to: '/decisions', label: 'Decisions', icon: '◎' },
  { to: '/backtest', label: 'Backtest', icon: '⟳' },
]

function PipelineStatusBadge({ status }: { status: string | null }) {
  if (!status) return null

  const configs: Record<string, { color: string; dot: string; label: string }> = {
    RUNNING: {
      color: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
      dot: 'bg-yellow-400 animate-pulse',
      label: 'Running',
    },
    SUCCESS: {
      color: 'text-gain bg-gain/10 border-gain/30',
      dot: 'bg-gain',
      label: 'Success',
    },
    FAILED: {
      color: 'text-loss bg-loss/10 border-loss/30',
      dot: 'bg-loss',
      label: 'Failed',
    },
  }

  const cfg = configs[status.toUpperCase()] ?? {
    color: 'text-gray-400 bg-gray-700 border-gray-600',
    dot: 'bg-gray-400',
    label: status,
  }

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded border ${cfg.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

export function Sidebar() {
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [triggerError, setTriggerError] = useState<string | null>(null)

  const pollStatus = useCallback(async () => {
    try {
      const status = await fetchPipelineStatus()
      setPipelineStatus(status)
    } catch {
      // Silent fail for background polling
    }
  }, [])

  useEffect(() => {
    pollStatus()
    const interval = setInterval(pollStatus, 15_000)
    return () => clearInterval(interval)
  }, [pollStatus])

  const handleTriggerPipeline = async () => {
    setTriggering(true)
    setTriggerError(null)
    try {
      await triggerPipeline()
      // Poll immediately after trigger
      setTimeout(pollStatus, 1000)
    } catch (err) {
      setTriggerError(err instanceof Error ? err.message : 'Failed to trigger pipeline')
    } finally {
      setTriggering(false)
    }
  }

  const lastRun = pipelineStatus?.last_run

  return (
    <aside
      className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0 overflow-y-auto"
      role="navigation"
      aria-label="Main navigation"
    >
      {/* Logo / Brand */}
      <div className="px-4 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-blue-400 text-xl" aria-hidden="true">◈</span>
          <div>
            <span className="text-white font-bold text-sm tracking-wide">SpeculAI</span>
            <p className="text-gray-500 text-xs">Trading Dashboard</p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-2 py-4 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                isActive
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
              }`
            }
          >
            <span className="text-base" aria-hidden="true">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Pipeline Status Panel */}
      <div className="px-3 py-4 border-t border-gray-800 space-y-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 px-1">
          Pipeline
        </div>

        {/* Status badge */}
        <div className="flex items-center justify-between px-1">
          <span className="text-xs text-gray-400">Last status</span>
          <PipelineStatusBadge status={pipelineStatus?.status ?? null} />
        </div>

        {/* Last run info */}
        {lastRun && (
          <div className="bg-gray-800 rounded-md p-2.5 space-y-1.5 text-xs">
            <div className="flex justify-between text-gray-400">
              <span>Analyzed</span>
              <span className="font-mono text-gray-200">{lastRun.stocks_analyzed}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Candidates</span>
              <span className="font-mono text-gray-200">{lastRun.candidates_screened}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Approved</span>
              <span className="font-mono text-gain">{lastRun.trades_approved}</span>
            </div>
            <div className="flex justify-between text-gray-400">
              <span>Executed</span>
              <span className="font-mono text-blue-400">{lastRun.trades_executed}</span>
            </div>
            {lastRun.completed_at && (
              <div className="pt-1 border-t border-gray-700 text-gray-500">
                {new Date(lastRun.completed_at).toLocaleString('en-GB', {
                  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                })}
              </div>
            )}
            {lastRun.errors.length > 0 && (
              <div className="pt-1 border-t border-gray-700">
                <span className="text-loss">{lastRun.errors.length} error{lastRun.errors.length !== 1 ? 's' : ''}</span>
              </div>
            )}
          </div>
        )}

        {!pipelineStatus?.last_run && !pipelineStatus?.status && (
          <p className="text-xs text-gray-600 italic px-1">No pipeline run yet.</p>
        )}

        {/* Trigger button */}
        <button
          onClick={handleTriggerPipeline}
          disabled={triggering || pipelineStatus?.status === 'RUNNING'}
          className="w-full px-3 py-2 text-xs font-medium rounded-md bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white transition-colors"
          aria-label="Trigger pipeline run manually"
        >
          {triggering ? 'Triggering...' : pipelineStatus?.status === 'RUNNING' ? 'Pipeline running...' : 'Run Pipeline'}
        </button>

        {triggerError && (
          <p className="text-xs text-loss px-1">{triggerError}</p>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-800">
        <p className="text-xs text-gray-600">
          Paper trading only
        </p>
      </div>
    </aside>
  )
}

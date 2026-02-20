/**
 * ActionBadge — colored badge for trade/decision action labels.
 *
 * Usage:
 *   <ActionBadge action="BUY" />
 *   <ActionBadge action="SELL" size="lg" />
 *   <ActionBadge action="HOLD" size="sm" />
 */

import type { Action } from '@/types'

interface ActionBadgeProps {
  action: string
  size?: 'sm' | 'md' | 'lg'
}

const ACTION_STYLES: Record<string, string> = {
  BUY: 'bg-gain/20 text-gain border border-gain/40',
  SELL: 'bg-loss/20 text-loss border border-loss/40',
  HOLD: 'bg-gray-700/60 text-gray-300 border border-gray-600',
}

const SIZE_STYLES = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
}

export function ActionBadge({ action, size = 'md' }: ActionBadgeProps) {
  const normalized = action?.toUpperCase() as Action
  const colorClass = ACTION_STYLES[normalized] ?? ACTION_STYLES['HOLD']
  const sizeClass = SIZE_STYLES[size]

  return (
    <span
      className={`inline-flex items-center rounded font-semibold uppercase tracking-wider font-mono ${colorClass} ${sizeClass}`}
      role="status"
      aria-label={`Action: ${normalized}`}
    >
      {normalized}
    </span>
  )
}

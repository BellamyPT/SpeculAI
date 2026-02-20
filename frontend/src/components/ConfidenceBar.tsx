/**
 * ConfidenceBar — horizontal progress bar displaying a 0–1 confidence value.
 *
 * Usage:
 *   <ConfidenceBar value={0.87} />
 *   <ConfidenceBar value={0.45} showLabel />
 */

interface ConfidenceBarProps {
  /** Confidence value from 0 to 1 */
  value: number | string
  showLabel?: boolean
  className?: string
}

function getBarColor(pct: number): string {
  if (pct >= 0.75) return 'bg-gain'
  if (pct >= 0.5) return 'bg-yellow-500'
  return 'bg-loss'
}

export function ConfidenceBar({ value, showLabel = true, className = '' }: ConfidenceBarProps) {
  const numeric = typeof value === 'string' ? parseFloat(value) : value
  const clamped = Math.max(0, Math.min(1, isNaN(numeric) ? 0 : numeric))
  const pct = Math.round(clamped * 100)
  const barColor = getBarColor(clamped)

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Confidence: ${pct}%`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-mono text-gray-300 w-9 text-right tabular-nums">
          {pct}%
        </span>
      )}
    </div>
  )
}

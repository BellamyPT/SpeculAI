/**
 * MemoryReferencesPanel — displays past decision memory context items.
 * Filters context_items by context_type === 'memory'.
 *
 * Usage:
 *   <MemoryReferencesPanel items={decisionDetail.context_items} />
 */

import type { DecisionContextItemResponse } from '@/types'
import { ActionBadge } from '@/components/ActionBadge'

interface MemoryReferencesPanelProps {
  items: DecisionContextItemResponse[]
}

function parseMemoryContent(content: string): Record<string, string> | null {
  try {
    const parsed = JSON.parse(content)
    if (typeof parsed === 'object' && parsed !== null) {
      return Object.fromEntries(
        Object.entries(parsed).map(([k, v]) => [k, String(v)])
      )
    }
  } catch {
    // Not JSON — display as plain text
  }
  return null
}

function RelevanceBadge({ score }: { score: string | null }) {
  if (!score) return null
  const n = parseFloat(score)
  if (isNaN(n)) return null

  const color = n >= 0.7 ? 'text-gain bg-gain/10 border-gain/30'
    : n >= 0.4 ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30'
    : 'text-gray-400 bg-gray-700 border-gray-600'

  return (
    <span className={`text-xs font-mono px-1.5 py-0.5 rounded border ${color}`}>
      {Math.round(n * 100)}% similar
    </span>
  )
}

export function MemoryReferencesPanel({ items }: MemoryReferencesPanelProps) {
  const memoryItems = items.filter((item) => item.context_type === 'memory')

  if (memoryItems.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic py-4 text-center">
        No memory references retrieved for this decision.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {memoryItems.map((item) => {
        const parsed = parseMemoryContent(item.content)

        return (
          <div
            key={item.id}
            className="p-3 rounded-lg bg-gray-800 border border-gray-700 hover:border-gray-600 transition-colors"
          >
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Past decision:</span>
                <span className="text-xs font-mono text-gray-300">{item.source}</span>
                {parsed?.action && <ActionBadge action={parsed.action} size="sm" />}
              </div>
              <RelevanceBadge score={item.relevance_score} />
            </div>

            {parsed ? (
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                {parsed.outcome_pnl && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Outcome P&L:</span>
                    <span className={`font-mono ${parseFloat(parsed.outcome_pnl) >= 0 ? 'text-gain' : 'text-loss'}`}>
                      {parseFloat(parsed.outcome_pnl).toFixed(2)}
                    </span>
                  </div>
                )}
                {parsed.confidence && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Confidence:</span>
                    <span className="font-mono text-gray-300">{(parseFloat(parsed.confidence) * 100).toFixed(0)}%</span>
                  </div>
                )}
                {parsed.created_at && (
                  <div className="flex justify-between col-span-2">
                    <span className="text-gray-500">Date:</span>
                    <span className="font-mono text-gray-300 text-xs">
                      {new Date(parsed.created_at).toLocaleDateString('en-GB')}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-300 leading-relaxed">{item.content}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}

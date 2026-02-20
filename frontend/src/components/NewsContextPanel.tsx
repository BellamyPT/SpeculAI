/**
 * NewsContextPanel — displays news context items from a decision report.
 * Filters context_items by context_type === 'news'.
 *
 * Usage:
 *   <NewsContextPanel items={decisionDetail.context_items} />
 */

import type { DecisionContextItemResponse } from '@/types'

interface NewsContextPanelProps {
  items: DecisionContextItemResponse[]
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
      {Math.round(n * 100)}% match
    </span>
  )
}

export function NewsContextPanel({ items }: NewsContextPanelProps) {
  const newsItems = items.filter((item) => item.context_type === 'news')

  if (newsItems.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic py-4 text-center">
        No news context items for this decision.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {newsItems.map((item) => (
        <div
          key={item.id}
          className="p-3 rounded-lg bg-gray-800 border border-gray-700 hover:border-gray-600 transition-colors"
        >
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <span className="text-xs font-medium text-blue-400 truncate">
              {item.source || 'Unknown source'}
            </span>
            <RelevanceBadge score={item.relevance_score} />
          </div>
          <p className="text-sm text-gray-300 leading-relaxed">{item.content}</p>
        </div>
      ))}
    </div>
  )
}

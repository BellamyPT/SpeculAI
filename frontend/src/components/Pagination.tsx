/**
 * Pagination — prev/next controls with page info display.
 *
 * Usage:
 *   <Pagination
 *     total={150}
 *     limit={50}
 *     offset={0}
 *     onOffsetChange={(offset) => setOffset(offset)}
 *   />
 */

interface PaginationProps {
  total: number
  limit: number
  offset: number
  onOffsetChange: (offset: number) => void
  className?: string
}

export function Pagination({ total, limit, offset, onOffsetChange, className = '' }: PaginationProps) {
  const currentPage = Math.floor(offset / limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / limit))
  const hasPrev = offset > 0
  const hasNext = offset + limit < total

  const goToPrev = () => {
    if (hasPrev) onOffsetChange(Math.max(0, offset - limit))
  }

  const goToNext = () => {
    if (hasNext) onOffsetChange(offset + limit)
  }

  const start = total === 0 ? 0 : offset + 1
  const end = Math.min(offset + limit, total)

  return (
    <div className={`flex items-center justify-between px-1 ${className}`}>
      <span className="text-sm text-gray-400 tabular-nums">
        {total === 0
          ? 'No results'
          : `Showing ${start}–${end} of ${total.toLocaleString()}`}
      </span>

      <div className="flex items-center gap-1" role="navigation" aria-label="Pagination">
        <button
          onClick={goToPrev}
          disabled={!hasPrev}
          className="px-3 py-1.5 text-sm rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Previous page"
        >
          Prev
        </button>

        <span className="px-3 py-1.5 text-sm text-gray-400 tabular-nums">
          {currentPage} / {totalPages}
        </span>

        <button
          onClick={goToNext}
          disabled={!hasNext}
          className="px-3 py-1.5 text-sm rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Next page"
        >
          Next
        </button>
      </div>
    </div>
  )
}

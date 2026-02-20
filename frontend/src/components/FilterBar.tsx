/**
 * FilterBar — reusable horizontal filter row for list pages.
 *
 * Accepts an array of filter field definitions and renders the
 * appropriate input type for each (text, select, date, number).
 *
 * Usage:
 *   <FilterBar
 *     fields={[
 *       { key: 'ticker', label: 'Ticker', type: 'text', placeholder: 'e.g. AAPL' },
 *       { key: 'side', label: 'Side', type: 'select', options: [
 *         { value: '', label: 'All sides' },
 *         { value: 'BUY', label: 'BUY' },
 *       ]},
 *     ]}
 *     values={{ ticker: '', side: '' }}
 *     onChange={(key, value) => setFilters(f => ({ ...f, [key]: value }))}
 *     onReset={() => setFilters(defaultFilters)}
 *   />
 */

export interface FilterFieldOption {
  value: string
  label: string
}

export type FilterFieldType = 'text' | 'select' | 'date' | 'number'

export interface FilterField {
  key: string
  label: string
  type: FilterFieldType
  placeholder?: string
  options?: FilterFieldOption[]
  min?: number
  max?: number
  step?: number
}

interface FilterBarProps {
  fields: FilterField[]
  values: Record<string, string | number>
  onChange: (key: string, value: string | number) => void
  onReset: () => void
  className?: string
}

const inputBase =
  'bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors w-full'

export function FilterBar({ fields, values, onChange, onReset, className = '' }: FilterBarProps) {
  return (
    <div className={`flex flex-wrap items-end gap-3 ${className}`} role="search" aria-label="Filters">
      {fields.map((field) => (
        <div key={field.key} className="flex flex-col gap-1 min-w-[130px]">
          <label
            htmlFor={`filter-${field.key}`}
            className="text-xs text-gray-400 font-medium uppercase tracking-wider"
          >
            {field.label}
          </label>

          {field.type === 'select' ? (
            <select
              id={`filter-${field.key}`}
              value={String(values[field.key] ?? '')}
              onChange={(e) => onChange(field.key, e.target.value)}
              className={`${inputBase} cursor-pointer`}
            >
              {field.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : field.type === 'number' ? (
            <input
              id={`filter-${field.key}`}
              type="number"
              min={field.min}
              max={field.max}
              step={field.step ?? 0.01}
              placeholder={field.placeholder}
              value={values[field.key] ?? ''}
              onChange={(e) => onChange(field.key, e.target.value === '' ? '' : parseFloat(e.target.value))}
              className={inputBase}
            />
          ) : (
            <input
              id={`filter-${field.key}`}
              type={field.type}
              placeholder={field.placeholder}
              value={String(values[field.key] ?? '')}
              onChange={(e) => onChange(field.key, e.target.value)}
              className={inputBase}
            />
          )}
        </div>
      ))}

      <button
        onClick={onReset}
        className="px-3 py-1.5 text-sm rounded bg-gray-700 text-gray-300 border border-gray-600 hover:bg-gray-600 hover:text-white transition-colors self-end"
        aria-label="Reset all filters"
      >
        Reset
      </button>
    </div>
  )
}

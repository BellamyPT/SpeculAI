/**
 * TechnicalIndicatorsPanel — displays RSI, MACD, Bollinger Bands, and
 * SMA/EMA values parsed from a decision report's technical_summary JSONB field.
 *
 * Usage:
 *   <TechnicalIndicatorsPanel data={decisionDetail.technical_summary} />
 */

interface TechnicalIndicatorsPanelProps {
  data: Record<string, unknown>
}

function formatValue(value: unknown, decimals = 2): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toFixed(decimals)
  if (typeof value === 'string') {
    const n = parseFloat(value)
    return isNaN(n) ? value : n.toFixed(decimals)
  }
  return String(value)
}

function getRsiColor(value: unknown): string {
  const n = typeof value === 'number' ? value : parseFloat(String(value))
  if (isNaN(n)) return 'text-gray-300'
  if (n >= 70) return 'text-loss'
  if (n <= 30) return 'text-gain'
  return 'text-gray-100'
}

interface IndicatorRowProps {
  label: string
  value: string
  valueClass?: string
  note?: string
}

function IndicatorRow({ label, value, valueClass = 'text-gray-100', note }: IndicatorRowProps) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-700/50 last:border-0">
      <span className="text-sm text-gray-400">{label}</span>
      <div className="flex items-center gap-2">
        {note && <span className="text-xs text-gray-500 italic">{note}</span>}
        <span className={`text-sm font-mono tabular-nums font-medium ${valueClass}`}>{value}</span>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h4 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">{title}</h4>
      <div>{children}</div>
    </div>
  )
}

export function TechnicalIndicatorsPanel({ data }: TechnicalIndicatorsPanelProps) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="text-sm text-gray-500 italic py-4 text-center">
        No technical data available for this report.
      </div>
    )
  }

  const rsi = data['rsi'] ?? data['RSI']
  const macd = data['macd'] ?? data['MACD']
  const macdSignal = data['macd_signal'] ?? data['signal']
  const macdHist = data['macd_hist'] ?? data['histogram']
  const bbUpper = data['bb_upper'] ?? data['bollinger_upper']
  const bbMiddle = data['bb_middle'] ?? data['bollinger_middle']
  const bbLower = data['bb_lower'] ?? data['bollinger_lower']
  const sma20 = data['sma_20'] ?? data['SMA20'] ?? data['sma20']
  const sma50 = data['sma_50'] ?? data['SMA50'] ?? data['sma50']
  const sma200 = data['sma_200'] ?? data['SMA200'] ?? data['sma200']
  const ema12 = data['ema_12'] ?? data['EMA12'] ?? data['ema12']
  const ema26 = data['ema_26'] ?? data['EMA26'] ?? data['ema26']
  const volume = data['volume'] ?? data['Volume']
  const price = data['close'] ?? data['price'] ?? data['current_price']
  const atr = data['atr'] ?? data['ATR']

  return (
    <div>
      {price !== undefined && (
        <Section title="Price">
          <IndicatorRow label="Close / Current" value={formatValue(price)} />
          {atr !== undefined && <IndicatorRow label="ATR (volatility)" value={formatValue(atr)} />}
          {volume !== undefined && (
            <IndicatorRow label="Volume" value={typeof volume === 'number' ? volume.toLocaleString() : String(volume)} />
          )}
        </Section>
      )}

      {rsi !== undefined && (
        <Section title="Momentum — RSI">
          <IndicatorRow
            label="RSI (14)"
            value={formatValue(rsi)}
            valueClass={getRsiColor(rsi)}
            note={
              typeof rsi === 'number'
                ? rsi >= 70 ? 'Overbought'
                : rsi <= 30 ? 'Oversold'
                : 'Neutral'
                : undefined
            }
          />
        </Section>
      )}

      {(macd !== undefined || macdSignal !== undefined) && (
        <Section title="Trend — MACD">
          {macd !== undefined && <IndicatorRow label="MACD Line" value={formatValue(macd)} />}
          {macdSignal !== undefined && <IndicatorRow label="Signal Line" value={formatValue(macdSignal)} />}
          {macdHist !== undefined && (
            <IndicatorRow
              label="Histogram"
              value={formatValue(macdHist)}
              valueClass={
                typeof macdHist === 'number'
                  ? macdHist >= 0 ? 'text-gain' : 'text-loss'
                  : 'text-gray-100'
              }
            />
          )}
        </Section>
      )}

      {(bbUpper !== undefined || bbMiddle !== undefined || bbLower !== undefined) && (
        <Section title="Volatility — Bollinger Bands (20,2)">
          {bbUpper !== undefined && <IndicatorRow label="Upper Band" value={formatValue(bbUpper)} />}
          {bbMiddle !== undefined && <IndicatorRow label="Middle (SMA20)" value={formatValue(bbMiddle)} />}
          {bbLower !== undefined && <IndicatorRow label="Lower Band" value={formatValue(bbLower)} />}
        </Section>
      )}

      {(sma20 !== undefined || sma50 !== undefined || sma200 !== undefined || ema12 !== undefined || ema26 !== undefined) && (
        <Section title="Moving Averages">
          {sma20 !== undefined && <IndicatorRow label="SMA 20" value={formatValue(sma20)} />}
          {sma50 !== undefined && <IndicatorRow label="SMA 50" value={formatValue(sma50)} />}
          {sma200 !== undefined && <IndicatorRow label="SMA 200" value={formatValue(sma200)} />}
          {ema12 !== undefined && <IndicatorRow label="EMA 12" value={formatValue(ema12)} />}
          {ema26 !== undefined && <IndicatorRow label="EMA 26" value={formatValue(ema26)} />}
        </Section>
      )}

      {/* Fallback: render any remaining keys not covered above */}
      {(() => {
        const knownKeys = new Set([
          'rsi', 'RSI', 'macd', 'MACD', 'macd_signal', 'signal', 'macd_hist', 'histogram',
          'bb_upper', 'bollinger_upper', 'bb_middle', 'bollinger_middle', 'bb_lower', 'bollinger_lower',
          'sma_20', 'SMA20', 'sma20', 'sma_50', 'SMA50', 'sma50', 'sma_200', 'SMA200', 'sma200',
          'ema_12', 'EMA12', 'ema12', 'ema_26', 'EMA26', 'ema26',
          'volume', 'Volume', 'close', 'price', 'current_price', 'atr', 'ATR',
        ])
        const extra = Object.entries(data).filter(([k]) => !knownKeys.has(k))
        if (extra.length === 0) return null
        return (
          <Section title="Additional Indicators">
            {extra.map(([key, val]) => (
              <IndicatorRow key={key} label={key.replace(/_/g, ' ')} value={formatValue(val)} />
            ))}
          </Section>
        )
      })()}
    </div>
  )
}

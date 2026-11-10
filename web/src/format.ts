import type { MouseEvent } from 'react'

import type { CriterionResult, HistoryRow, Progress, Quality } from './types'

/** Format elapsed or remaining seconds as a compact duration. */
export function duration(seconds: number): string {
  const s = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}m`
}

/** Row click handler that does what the row's ticker link or button does. The ticker stays the
 * keyboard target; clicks on other controls and text selections are left alone. */
export function progressLabels(step: Progress, nowSeconds: number) {
  const counter = step.total > 0 ? `${step.done} of ${step.total}` : null
  const eta = step.eta_seconds == null ? null : duration(
    step.eta_seconds < 60 ? Math.round(step.eta_seconds / 5) * 5 : step.eta_seconds,
  )
  return {
    counter,
    timing: `${step.started_at == null ? "Elapsed ?" : `Elapsed ${duration(nowSeconds - step.started_at)}`}${eta === null ? '' : ` · About ${eta} left`}`,
    valueText: [counter, eta === null ? null : `about ${eta} left`].filter(Boolean).join(', ') || undefined,
  }
}

export function rowClick(action: () => void) {
  return (e: MouseEvent) => {
    if ((e.target as Element).closest('a, button, input, select, textarea') || window.getSelection()?.toString()) return
    action()
  }
}

/** Row click that opens the ticker's History page. */
export const toHistory = (ticker: string) =>
  rowClick(() => {
    window.location.hash = `#history/${encodeURIComponent(ticker)}`
  })

/** '2026-10-20T15:04:00' -> '2026-10-20 15:04' */
export const when = (iso: string) => iso.replace('T', ' ').slice(0, 16)

/** Today's local date as YYYY-MM-DD, for file names (the Swedish locale writes ISO dates). */
export const today = () => new Date().toLocaleDateString('sv')

/** Saves a file built in the page or received from the API. */
export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

/** history.py saves fundamentals, Next earnings, technical; like Analysis, Next earnings counts as fundamental. */
export function groups(criteria: CriterionResult[]) {
  const i = criteria.findIndex((c) => c.name === 'Next earnings') + 1
  return { fundamental: criteria.slice(0, i), technical: criteria.slice(i) }
}

/** The latest saved analysis of each ticker, newest first. */
export function latestByTicker(rows: HistoryRow[]): HistoryRow[] {
  const last = new Map<string, HistoryRow>()
  for (const r of rows) if (!last.has(r.ticker) || r.analyzed_at >= last.get(r.ticker)!.analyzed_at) last.set(r.ticker, r)
  return [...last.values()].sort((a, b) => b.analyzed_at.localeCompare(a.analyzed_at))
}

/** Number with fixed decimals, or N/D when missing. */
export function fmt(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined
    ? 'N/D'
    : v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Percent with one decimal ("31.2%"), or N/D. */
export function pct(v: number | null): string {
  return v === null ? 'N/D' : `${v.toFixed(1)}%`
}

/** Signed percentage points ("+4.1 pt"), or N/D. */
export function points(v: number | null): string {
  return v === null ? 'N/D' : `${v >= 0 ? '+' : ''}${v.toFixed(1)} pt`
}

/** Same text as the terminal (report.quality_text). */
export function qualityText(q: Quality): string {
  return `ROIC ${pct(q.roic_pct)}, op. margin ${points(q.margin_change_pt)}`
}

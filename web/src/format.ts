import type { Quality } from './types'

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

/** Number with fixed decimals, or N/D when missing. */
export function fmt(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined
    ? 'N/D'
    : v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

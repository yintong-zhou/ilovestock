import type { Progress } from './types'

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h ? `${h}h ${m}m` : m ? `${m}m ${s % 60}s` : `${s}s`
}

export function progressDetails(step: Progress, now: number): string {
  const elapsed = step.started_at != null && Number.isFinite(step.started_at)
    ? formatDuration(now - step.started_at) : '—'
  const eta = step.eta_seconds != null && Number.isFinite(step.eta_seconds)
    ? formatDuration(step.eta_seconds) : 'calculating…'
  return `Elapsed: ${elapsed} · Estimated remaining: ${eta}`
}

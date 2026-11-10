import { describe, expect, it } from 'vitest'
import { formatDuration, progressDetails } from './progressFormat'

describe('progress formatting', () => {
  it('formats durations and clamps negative values', () => {
    expect(formatDuration(-1)).toBe('0s')
    expect(formatDuration(65)).toBe('1m 5s')
    expect(formatDuration(3660)).toBe('1h 1m')
  })
  it('handles missing fields and displays elapsed and estimate', () => {
    expect(progressDetails({ text: '', done: 0, total: 0 }, 100)).toBe('Elapsed: — · Estimated remaining: calculating…')
    expect(progressDetails({ text: '', done: 2, total: 4, started_at: 90, eta_seconds: 30 }, 100))
      .toBe('Elapsed: 10s · Estimated remaining: 30s')
  })
})

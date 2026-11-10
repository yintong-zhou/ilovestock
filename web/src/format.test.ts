import { describe, expect, it } from 'vitest'

import { duration, progressLabels } from './format'

describe('duration', () => {
  it.each([
    [0, '0s'], [59, '59s'], [60, '1m 00s'], [3599, '59m 59s'],
    [3600, '1h 00m'], [3720, '1h 02m'], [-1, '0s'], [NaN, '0s'],
    [Infinity, '0s'],
  ])('formats %s seconds as %s', (seconds, expected) => {
    expect(duration(seconds)).toBe(expected)
  })
})

describe('progressLabels', () => {
  const step = { text: 'Working', done: 2, total: 10, started_at: 100, eta_seconds: null as number | null }
  it('omits the counter for an unknown total', () => {
    expect(progressLabels({ ...step, total: 0 }, 110)).toEqual({ counter: null, timing: 'Elapsed 10s', valueText: undefined })
  })
  it('omits an unavailable estimate', () => {
    expect(progressLabels(step, 110)).toEqual({ counter: '2 of 10', timing: 'Elapsed 10s', valueText: '2 of 10' })
  })
  it('rounds a short estimate', () => {
    expect(progressLabels({ ...step, eta_seconds: 23 }, 110)).toEqual({ counter: '2 of 10', timing: 'Elapsed 10s · About 25s left', valueText: '2 of 10, about 25s left' })
  })
  it('shows completed counts and a zero estimate', () => {
    expect(progressLabels({ ...step, done: 10, eta_seconds: 0 }, 110).valueText).toBe('10 of 10, about 0s left')
  })
})

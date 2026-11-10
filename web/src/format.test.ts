import { describe, expect, it } from 'vitest'

import { duration } from './format'

describe('duration', () => {
  it.each([
    [0, '0s'], [59, '59s'], [60, '1m 00s'], [3599, '59m 59s'],
    [3600, '1h 00m'], [3720, '1h 02m'], [-1, '0s'], [NaN, '0s'],
    [Infinity, '0s'],
  ])('formats %s seconds as %s', (seconds, expected) => {
    expect(duration(seconds)).toBe(expected)
  })
})

import { describe, expect, it } from 'vitest'
import { type Frame, linePath, niceTicks, yRange } from './plotGeometry'

const frame: Frame = { x: [0, 10], y: [0, 10], width: 100, height: 100 }

describe('yRange', () => {
  it('uses the block domain when given', () => {
    expect(yRange([[[0, 50]]], [0, 12])).toEqual([0, 12])
  })

  it('pads the data extent and ignores missing values', () => {
    expect(yRange([[[0, 0], [1, null], [2, 10]]], null)).toEqual([-0.5, 10.5])
  })

  it('widens a flat series', () => {
    expect(yRange([[[0, 3], [1, 3]]], null)).toEqual([2, 4])
  })

  it('falls back when there is no data', () => {
    expect(yRange([[[0, null]]], null)).toEqual([-1, 1])
  })
})

describe('niceTicks', () => {
  it('picks round steps', () => {
    // The step is the smallest 1, 2, or 5 times a power of ten that is at least range / 5.
    expect(niceTicks([0, 3.2])).toEqual([0, 1, 2, 3])
    expect(niceTicks([0, 12])).toEqual([0, 5, 10])
    expect(niceTicks([-1, 1])).toEqual([-1, -0.5, 0, 0.5, 1])
    expect(niceTicks([0, 1000])).toEqual([0, 200, 400, 600, 800, 1000])
  })

  it('avoids floating point noise and negative zero', () => {
    // 3 * 0.1 is 0.30000000000000004 in floating point.
    expect(niceTicks([0, 0.5])).toEqual([0, 0.1, 0.2, 0.3, 0.4, 0.5])
    // Math.ceil(-0.25) is -0; rounding through toPrecision drops the sign.
    const ticks = niceTicks([-0.05, 0.5])
    expect(ticks).toEqual([0, 0.2, 0.4])
    expect(Object.is(ticks[0], -0)).toBe(false)
  })
})

describe('linePath', () => {
  it('maps points into the frame with y pointing up', () => {
    expect(linePath([[0, 0], [10, 10]], frame)).toBe('M0.00,100.00L100.00,0.00')
  })

  it('breaks the line at missing values', () => {
    expect(linePath([[0, 0], [5, null], [10, 10]], frame)).toBe('M0.00,100.00M100.00,0.00')
  })

  it('breaks the line across a jump taller than the y range', () => {
    expect(linePath([[0, 50], [5, -50]], frame)).toBe('M0.00,-400.00M50.00,600.00')
  })
})

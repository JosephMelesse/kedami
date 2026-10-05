import { describe, expect, it } from 'vitest'
import { dayProgress, splitDays } from './days'

/** Blocks named a, b, c, ... starting at the given page positions. */
function blocks(...tops: number[]) {
  return tops.map((top, index) => ({ id: String.fromCharCode(97 + index), top }))
}

describe('splitDays', () => {
  it('cuts at the block boundaries nearest to equal heights', () => {
    // 0 to 1000 in three days: targets at 333 and 667.
    expect(splitDays(blocks(0, 100, 300, 400, 700, 900), 1000, 3)).toEqual(['c', 'e'])
  })

  it('prefers the earlier boundary on a tie', () => {
    expect(splitDays(blocks(0, 400, 600), 1000, 2)).toEqual(['b'])
  })

  it('gives each day at least one block when a tall block covers several targets', () => {
    // One block runs from 100 to 950, so the targets at 250, 500, and 750 all fall inside it.
    expect(splitDays(blocks(0, 100, 950, 980), 1000, 4)).toEqual(['b', 'c', 'd'])
  })

  it('gives one day per block when asked for more days than blocks', () => {
    expect(splitDays(blocks(0, 10, 20), 30, 30)).toEqual(['b', 'c'])
  })

  it('makes no lines for one day, one block, or no blocks', () => {
    expect(splitDays(blocks(0, 500), 1000, 1)).toEqual([])
    expect(splitDays(blocks(0), 1000, 5)).toEqual([])
    expect(splitDays([], 0, 5)).toEqual([])
  })

  it('measures from where the first block starts, not the page top', () => {
    // 400 to 1000 in two days: the target is 700.
    expect(splitDays(blocks(400, 600, 750), 1000, 2)).toEqual(['c'])
  })
})

describe('dayProgress', () => {
  const lines = [1000, 2000]

  it('fills from the lesson start toward the first line', () => {
    expect(dayProgress(lines, 200, 3000, 600)).toEqual({ reached: 0, fill: 0.5 })
  })

  it('passes a line once the reading point reaches it, and starts the next day empty', () => {
    expect(dayProgress(lines, 0, 3000, 999).reached).toBe(0)
    expect(dayProgress(lines, 0, 3000, 1000)).toEqual({ reached: 1, fill: 0 })
    expect(dayProgress(lines, 0, 3000, 1500)).toEqual({ reached: 1, fill: 0.5 })
  })

  it('counts the end of a split lesson as its last line', () => {
    expect(dayProgress(lines, 0, 3000, 2999)).toEqual({ reached: 2, fill: 0.999 })
    expect(dayProgress(lines, 0, 3000, 3000)).toEqual({ reached: 3, fill: 1 })
    expect(dayProgress(lines, 0, 3000, 9000)).toEqual({ reached: 3, fill: 1 })
  })

  it('fills toward the end of a lesson with no lines, which reaches nothing', () => {
    expect(dayProgress([], 0, 2000, 500)).toEqual({ reached: 0, fill: 0.25 })
    expect(dayProgress([], 0, 2000, 2500)).toEqual({ reached: 0, fill: 1 })
  })

  it('shows no fill before the lesson starts', () => {
    expect(dayProgress(lines, 800, 3000, 300)).toEqual({ reached: 0, fill: 0 })
  })
})

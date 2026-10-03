import { beforeEach, describe, expect, it } from 'vitest'
import { loadDurations, saveDurations } from './durations'

describe('durations', () => {
  beforeEach(() => localStorage.clear())

  it('defaults to 25 and 5', () => {
    expect(loadDurations()).toEqual({ study: 25, rest: 5 })
  })

  it('round-trips saved durations', () => {
    saveDurations({ study: 50, rest: 10 })
    expect(loadDurations()).toEqual({ study: 50, rest: 10 })
  })

  it.each([
    ['not json', { study: 25, rest: 5 }],
    ['{"study": 0, "rest": 7}', { study: 25, rest: 7 }],
    ['{"study": 2.5, "rest": 999}', { study: 25, rest: 5 }],
    ['{"study": "30", "rest": 5}', { study: 25, rest: 5 }],
    ['null', { study: 25, rest: 5 }]
  ])('falls back per field for %s', (saved, expected) => {
    localStorage.setItem('kedami.pomodoro.durations', saved)
    expect(loadDurations()).toEqual(expected)
  })

  it('survives storage that throws', () => {
    const broken = { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('denied') } } as unknown as Storage
    expect(loadDurations(broken)).toEqual({ study: 25, rest: 5 })
    expect(() => saveDurations({ study: 30, rest: 5 }, broken)).not.toThrow()
  })
})

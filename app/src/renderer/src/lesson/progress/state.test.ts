import { describe, expect, it } from 'vitest'
import fixture from '../../../../../../server/fixtures/sample-lesson.json'
import type { ProgressRecord } from '../../api'
import type { Lesson } from '../types'
import { partState, problemCounts, toProgressMap } from './state'

const lesson = fixture as unknown as Lesson

function record(overrides: Partial<ProgressRecord>): ProgressRecord {
  return {
    block_id: 'ps3-4',
    part_id: 'a',
    status: 'not_started',
    last_response: null,
    attempts: 0,
    hints_used: 0,
    updated: null,
    ...overrides
  }
}

describe('partState', () => {
  it('is not started with no record', () => {
    expect(partState(undefined)).toBe('not_started')
  })

  it('is in progress after a hint with no answer', () => {
    expect(partState(record({ status: 'in_progress', hints_used: 1 }))).toBe('in_progress')
  })

  it('is wrong when in progress with a submitted answer', () => {
    expect(partState(record({ status: 'in_progress', last_response: '3', attempts: 1 }))).toBe('wrong')
  })

  it('keeps correct and marked done', () => {
    expect(partState(record({ status: 'correct', last_response: '2.36' }))).toBe('correct')
    expect(partState(record({ status: 'marked_done', last_response: '3' }))).toBe('marked_done')
  })
})

describe('problemCounts', () => {
  const done = (block_id: string, part_id: string | null, status: ProgressRecord['status'] = 'correct') =>
    record({ block_id, part_id, status })

  it('counts a problem only when every part is done', () => {
    const three = ['a', 'b', 'c'].map((p) => done('ps3-4', p))
    expect(problemCounts(lesson, toProgressMap(three))).toEqual({ done: 0, total: 2 })
    expect(problemCounts(lesson, toProgressMap([...three, done('ps3-4', 'd', 'marked_done')]))).toEqual({
      done: 1,
      total: 2
    })
  })

  it('ignores checkpoints and in-progress parts', () => {
    const records = [done('components-check', null), done('ps3-5', '5', 'in_progress')]
    expect(problemCounts(lesson, toProgressMap(records)).done).toBe(0)
  })
})

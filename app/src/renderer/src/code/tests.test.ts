import { describe, expect, it } from 'vitest'
import type { CodeTest } from '../lesson/types'
import { isFlagged, shownValue, submitPassed, unflagged } from './tests'

const tests: CodeTest[] = [
  { args: 'n = 1', expected: '1', compare: 'equal' },
  { args: 'n = 2', expected: '2', compare: 'equal' },
  { args: 'n = 3', expected: '3', compare: 'equal' }
]
const flag = (test: CodeTest) => ({ block_id: 'b', part_id: '1', args: test.args, expected: test.expected })

describe('flags', () => {
  it('match a test by both its arguments and its expected value', () => {
    expect(isFlagged(tests[0], [flag(tests[0])])).toBe(true)
    expect(isFlagged(tests[0], [{ ...flag(tests[0]), expected: '2' }])).toBe(false)
  })

  it('leave the other tests, numbered among all of them', () => {
    expect(unflagged(tests, [flag(tests[1])])).toEqual([
      { test: tests[0], number: 1 },
      { test: tests[2], number: 3 }
    ])
  })
})

describe('a Submit', () => {
  const pass = { passed: true, got: '1', output: '', error: null }
  it('passes only when the code loaded and every test ran and passed', () => {
    expect(submitPassed({ error: null, output: '', results: [pass, pass] }, 2)).toBe(true)
    expect(submitPassed({ error: null, output: '', results: [pass] }, 2)).toBe(false)
    expect(submitPassed({ error: null, output: '', results: [pass, { ...pass, passed: false }] }, 2)).toBe(false)
    expect(submitPassed({ error: 'SyntaxError', output: '', results: [] }, 0)).toBe(false)
  })
})

describe('shown values', () => {
  it.each([
    ['head = list_node([1, 2, 3])', 'head = [1, 2, 3]'],
    ['l1 = list_node([2, 4]), l2 = list_node([5])', 'l1 = [2, 4], l2 = [5]'],
    ['root = tree_node([1, None, 2]), k = 3', 'root = [1, None, 2], k = 3'],
    ['tree_node([])', '[]'],
    ['s = "list_node(x)"', 's = "list_node(x)"'],
    ['s = "a)b", head = list_node([1])', 's = "a)b", head = [1]'],
    ['nums = [3, 3], target = 6', 'nums = [3, 3], target = 6'],
    ['list_node([1, 2', 'list_node([1, 2']
  ])('%s shows as %s', (source, shown) => {
    expect(shownValue(source)).toBe(shown)
  })
})

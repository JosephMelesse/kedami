// Which tests Run and Submit use, and how a test's text is shown. See architecture/code-problems.md.

import type { TestFlag } from '../api'
import type { RunResult } from './harness'
import type { CodeTest } from '../lesson/types'

/** How many tests Run tries. */
export const RUN_TESTS = 3

export function isFlagged(test: CodeTest, flags: TestFlag[]): boolean {
  return flags.some((f) => f.args === test.args && f.expected === test.expected)
}

/** The tests that aren't flagged, in order, each with its number among all the problem's tests. */
export function unflagged(tests: CodeTest[], flags: TestFlag[]): { test: CodeTest; number: number }[] {
  return tests.map((test, i) => ({ test, number: i + 1 })).filter(({ test }) => !isFlagged(test, flags))
}

/** A Submit passes when every test it ran passed, it ran all of them, and the code loaded. */
export function submitPassed(result: RunResult, total: number): boolean {
  return result.error === null && result.results.length === total && result.results.every((r) => r.passed)
}

/** A test's arguments or expected value as LeetCode shows them: lists and trees as plain lists. */
export function shownValue(source: string): string {
  let shown = ''
  for (let i = 0; i < source.length; i++) {
    const c = source[i]
    if (c === '"' || c === "'") {
      const end = stringEnd(source, i)
      shown += source.slice(i, end + 1)
      i = end
      continue
    }
    const wrapper = WRAPPERS.find((w) => source.startsWith(w, i) && !/\w/.test(source[i - 1] ?? ''))
    const close = wrapper ? matchingParen(source, i + wrapper.length - 1) : -1
    if (wrapper && close !== -1) {
      shown += shownValue(source.slice(i + wrapper.length, close))
      i = close
      continue
    }
    shown += c
  }
  return shown
}

const WRAPPERS = ['list_node(', 'tree_node(']

/** The index of the quote that closes the string opening at `start`, or the last index if none does. */
function stringEnd(source: string, start: number): number {
  for (let i = start + 1; i < source.length; i++) {
    if (source[i] === '\\') i++
    else if (source[i] === source[start]) return i
  }
  return source.length - 1
}

function matchingParen(source: string, open: number): number {
  let depth = 0
  for (let i = open; i < source.length; i++) {
    const c = source[i]
    if (c === '"' || c === "'") i = stringEnd(source, i)
    else if (c === '(') depth++
    else if (c === ')' && --depth === 0) return i
  }
  return -1
}

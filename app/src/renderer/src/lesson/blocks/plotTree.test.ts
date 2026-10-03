import { describe, expect, it } from 'vitest'
import type { TreeNode } from '../../api'
import { evaluateTree, sampleTree } from './plotTree'

// a*x - x**2, as the server would send it.
const tree: TreeNode = {
  add: [{ mul: [{ sym: 'a' }, { sym: 'x' }] }, { mul: [{ num: -1 }, { pow: [{ sym: 'x' }, { num: 2 }] }] }]
}

describe('evaluateTree', () => {
  it('evaluates arithmetic with parameters', () => {
    expect(evaluateTree(tree, { a: 3, x: 2 })).toBe(2)
  })

  it('evaluates functions', () => {
    expect(evaluateTree({ fn: 'cos', arg: { num: 0 } }, {})).toBe(1)
    expect(evaluateTree({ fn: 'abs', arg: { num: -2 } }, {})).toBe(2)
  })

  it('gives NaN for unknown names, unknown functions, and non-real numbers', () => {
    expect(evaluateTree({ sym: 'q' }, {})).toBeNaN()
    expect(evaluateTree({ fn: 'eval', arg: { num: 1 } }, {})).toBeNaN()
    expect(evaluateTree({ num: null }, {})).toBeNaN()
  })
})

describe('sampleTree', () => {
  it('samples across the domain', () => {
    const points = sampleTree(tree, [0, 4], { a: 4 }, 5)
    expect(points).toEqual([
      [0, 0],
      [1, 3],
      [2, 4],
      [3, 3],
      [4, 0]
    ])
  })

  it('marks values that are not finite as missing', () => {
    const log: TreeNode = { fn: 'log', arg: { sym: 'x' } }
    expect(sampleTree(log, [-1, 1], {}, 3).map(([, y]) => y)).toEqual([null, null, 0])
  })
})

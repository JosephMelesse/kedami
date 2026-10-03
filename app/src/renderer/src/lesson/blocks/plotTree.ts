// Evaluates the expression trees the server sends for plots with parameters.
// Plain arithmetic over a fixed node set; nothing is ever run as code.
import type { TreeNode } from '../../api'
import type { Point, Range } from './plotGeometry'

const FUNCTIONS: Record<string, (value: number) => number> = {
  sin: Math.sin,
  cos: Math.cos,
  tan: Math.tan,
  asin: Math.asin,
  acos: Math.acos,
  atan: Math.atan,
  sinh: Math.sinh,
  cosh: Math.cosh,
  tanh: Math.tanh,
  exp: Math.exp,
  log: Math.log,
  abs: Math.abs
}

export function evaluateTree(node: TreeNode, values: Record<string, number>): number {
  if ('num' in node) return node.num ?? NaN
  if ('sym' in node) return values[node.sym] ?? NaN
  if ('add' in node) return node.add.reduce((sum, n) => sum + evaluateTree(n, values), 0)
  if ('mul' in node) return node.mul.reduce((product, n) => product * evaluateTree(n, values), 1)
  if ('pow' in node) return Math.pow(evaluateTree(node.pow[0], values), evaluateTree(node.pow[1], values))
  const fn = FUNCTIONS[node.fn]
  return fn ? fn(evaluateTree(node.arg, values)) : NaN
}

/** Sample a tree across x, with the parameters held at the given values. */
export function sampleTree(node: TreeNode, [start, end]: Range, parameters: Record<string, number>, count = 201): Point[] {
  return Array.from({ length: count }, (_, i) => {
    const x = start + ((end - start) * i) / (count - 1)
    const y = evaluateTree(node, { ...parameters, x })
    return [x, Number.isFinite(y) ? y : null]
  })
}

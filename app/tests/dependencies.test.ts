import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('KaTeX', () => {
  // The stylesheet comes from the app's katex package; the HTML comes from the copy rehype-katex
  // and remark-math use. Different versions draw accents like \\vec wrongly, so there must be one copy.
  it('is installed once, so its HTML matches its stylesheet', () => {
    const root = join(__dirname, '..')
    for (const owner of ['rehype-katex', 'micromark-extension-math']) {
      expect(existsSync(join(root, 'node_modules', owner, 'node_modules', 'katex'))).toBe(false)
    }
  })
})

describe('sortedcontainers', () => {
  // Vendored for the code runner. The hash is the one PyPI publishes for this wheel.
  it("is PyPI's wheel, unchanged", () => {
    const wheel = readFileSync(
      join(__dirname, '..', 'src/renderer/src/code/vendor/sortedcontainers-2.4.0-py2.py3-none-any.whl')
    )
    expect(createHash('sha256').update(wheel).digest('hex')).toBe(
      'a163dcaede0f1c021485e957a39245190e74249897e2ae4b2aa38595db237ee0'
    )
  })
})

import { existsSync } from 'node:fs'
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

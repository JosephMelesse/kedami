import { describe, expect, it } from 'vitest'
import { leetcodeProblemUrl } from '../src/main/links'

describe('leetcodeProblemUrl', () => {
  it.each([
    ['two-sum', 'https://leetcode.com/problems/two-sum/'],
    ['3sum', 'https://leetcode.com/problems/3sum/'],
    ['powx-n', 'https://leetcode.com/problems/powx-n/']
  ])('opens %s', (slug, url) => {
    expect(leetcodeProblemUrl(slug)).toBe(url)
  })

  it.each([
    '',
    'Two-Sum',
    'two sum',
    '../../evil',
    'two-sum/?x=1',
    'two-sum#frag',
    'https://evil.com',
    '-two-sum',
    'two--sum',
    'a'.repeat(201),
    42,
    null,
    undefined
  ])('refuses %s', (slug) => {
    expect(leetcodeProblemUrl(slug)).toBeNull()
  })
})

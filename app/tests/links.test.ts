import { describe, expect, it } from 'vitest'
import { leetcodeProblemUrl, pgexercisesPageUrl } from '../src/main/links'

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

describe('pgexercisesPageUrl', () => {
  it.each([
    ['joins/self2.html', 'https://pgexercises.com/questions/joins/self2.html'],
    ['aggregates/count3.html', 'https://pgexercises.com/questions/aggregates/count3.html'],
    ['date/utilisationpermonth.html', 'https://pgexercises.com/questions/date/utilisationpermonth.html']
  ])('opens %s', (path, url) => {
    expect(pgexercisesPageUrl(path)).toBe(url)
  })

  it.each([
    '',
    'self2.html',
    'joins/self2',
    'joins/self2.htm',
    'joins/self2.html?x=1',
    'joins/self2.html#top',
    '../joins/self2.html',
    'joins/../../etc.html',
    'joins/sub/self2.html',
    '/joins/self2.html',
    'Joins/self2.html',
    'joins/self-2.html',
    'https://evil.com/a.html',
    `joins/${'a'.repeat(100)}.html`,
    42,
    null,
    undefined
  ])('refuses %s', (path) => {
    expect(pgexercisesPageUrl(path)).toBeNull()
  })
})

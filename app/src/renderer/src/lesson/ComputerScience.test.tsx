import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { LessonView } from './LessonView'
import { ProgressProvider } from './progress/ProgressContext'
import type { Lesson } from './types'

const lesson = {
  schema_version: 1,
  id: 'cs',
  title: 'Hashing',
  subject: 'computer_science',
  source_files: ['problems.md'],
  sections: [
    {
      id: 'hash-maps',
      title: 'Hash maps',
      goal: 'Look things up in O(1).',
      blocks: [
        { type: 'explanation', id: 'e', body: '```python\ndef seen(xs):\n    return {x: True for x in xs}  # dict\n```' },
        {
          type: 'checkpoint',
          id: 'c',
          prompt: 'Lookup time in a dict?',
          answer: { kind: 'choice', options: ['O(1)', 'O(n)'], correct_index: 0 },
          hints: [],
          verified: false
        },
        {
          type: 'problem',
          id: 'leetcode-1',
          source_ref: 'LeetCode #1',
          prompt: '',
          parts: [
            {
              id: '1',
              label: '1',
              prompt: 'Complete LeetCode #1: Two Sum.',
              answer: { kind: 'external', platform: 'leetcode', number: 1, title: 'Two Sum', slug: 'two-sum' },
              hints: ['Think about what you have seen so far.'],
              verified: false
            }
          ]
        }
      ]
    }
  ]
} as unknown as Lesson

function render(): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(
    <ProgressProvider lessonId="cs" initial={[]}>
      <LessonView lesson={lesson} />
    </ProgressProvider>
  )
  return root
}

describe('a computer science lesson', () => {
  const root = render()
  const problem = [...root.querySelectorAll<HTMLElement>('.card')].find((c) => c.textContent?.includes('LeetCode #1'))!

  it('names the subject', () => {
    expect(root.querySelector('.lesson-header .eyebrow')?.textContent).toBe('Computer Science')
  })

  it('sends the LeetCode problem to the browser and finishes it with mark done', () => {
    expect(problem.textContent).toContain('Complete LeetCode #1: Two Sum.')
    const buttons = [...problem.querySelectorAll('button')].map((b) => b.textContent)
    expect(buttons).toEqual(['Open on LeetCode', 'Show hint 1 of 1', 'Mark done'])
    expect(problem.querySelector('input, textarea')).toBeNull()
  })

  it('never calls a LeetCode problem unverified', () => {
    expect(problem.textContent).not.toContain('Unverified answer')
    // The unverified checkpoint still says so.
    expect(root.textContent?.match(/Unverified answer/g)).toHaveLength(1)
  })

  it('highlights Python code', () => {
    const code = root.querySelector('pre code')!
    expect(code.className).toContain('language-python')
    expect([...code.querySelectorAll('.hljs-keyword')].map((k) => k.textContent)).toEqual(['def', 'return', 'for', 'in'])
    expect(code.querySelector('.hljs-comment')?.textContent).toBe('# dict')
  })
})

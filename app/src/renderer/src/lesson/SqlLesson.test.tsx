import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { renderToString } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { KedamiApi } from '../../../preload/api'
import { OpenWorkspace } from '../code/Workspace'
import { LessonView } from './LessonView'
import { ProgressProvider } from './progress/ProgressContext'
import type { Lesson } from './types'

const lesson = {
  schema_version: 1,
  id: 'sql',
  title: 'Queries',
  subject: 'computer_science',
  domain: 'sql',
  credits: [],
  source_files: ['problems.md'],
  sections: [
    {
      id: 'selecting',
      title: 'Selecting',
      goal: 'Read rows.',
      blocks: [
        { type: 'explanation', id: 'e', body: '```sql\nSELECT name FROM student WHERE year = 3;\n```' },
        {
          type: 'problem',
          id: 'ps2-1',
          source_ref: 'PS2 #1',
          prompt: '',
          parts: [
            {
              id: 'a',
              label: '(a)',
              prompt: 'List the names of students in year 3.',
              answer: { kind: 'query', database: 'course/school', reference: 'SELECT name FROM student WHERE year = 3', ordered: false, exercise: null },
              hints: [],
              verified: false
            }
          ]
        },
        {
          type: 'checkpoint',
          id: 'selecting-practice-1',
          prompt: 'How many singers are there?',
          answer: { kind: 'query', database: 'bank/music', reference: 'SELECT count(*) FROM singer', ordered: false, exercise: 'music-1' },
          hints: [],
          verified: false
        }
      ]
    }
  ]
} as unknown as Lesson

function render(): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(
    <ProgressProvider lessonId="sql" initial={[]}>
      <OpenWorkspace.Provider value={() => {}}>
        <LessonView lesson={lesson} />
      </OpenWorkspace.Provider>
    </ProgressProvider>
  )
  return root
}

const card = (root: HTMLElement, text: string) =>
  [...root.querySelectorAll<HTMLElement>('.card')].find((c) => c.textContent?.includes(text))!

describe('a SQL lesson', () => {
  const root = render()

  it('shows a query part with its text, Solve, and mark done, and says when it is unverified', () => {
    const problem = card(root, 'PS2 #1')
    expect(problem.textContent).toContain('List the names of students in year 3.')
    expect([...problem.querySelectorAll('button')].map((b) => b.textContent)).toEqual(['Solve', 'Mark done'])
    expect(problem.textContent).toContain('Unverified answer')
    expect(problem.querySelector('input, textarea')).toBeNull()
  })

  it('shows a practice checkpoint with Solve, no mark done, and never calls it unverified', () => {
    const practice = card(root, 'How many singers')
    expect([...practice.querySelectorAll('button')].map((b) => b.textContent)).toEqual(['Solve'])
    expect(practice.textContent).not.toContain('Unverified answer')
  })

  it('highlights SQL code', () => {
    const code = root.querySelector('pre code')!
    expect(code.className).toContain('language-sql')
    const keywords = [...code.querySelectorAll('.hljs-keyword')].map((k) => k.textContent)
    expect(keywords).toEqual(expect.arrayContaining(['SELECT', 'FROM', 'WHERE']))
    expect(keywords).not.toContain('student')
  })
})

const CREDIT =
  'Explanations draw on Structured Query Language, Wikibooks (CC BY-SA): en.wikibooks.org/wiki/Structured_Query_Language'

// A chapter lesson: recommended problems from the bank and pgexercises, with the book credited.
const chapterLesson = {
  ...lesson,
  credits: [CREDIT],
  sections: [
    {
      id: 'filtering',
      title: 'Filtering',
      goal: 'Keep matching rows.',
      blocks: [
        {
          type: 'problem',
          id: 'problem-1',
          source_ref: 'Problem 1',
          prompt: '',
          parts: [
            {
              id: '1',
              label: '1',
              prompt: 'Which singers are from PT?',
              answer: { kind: 'query', database: 'bank/music', reference: "SELECT name FROM singer WHERE country = 'PT'", ordered: false, exercise: 'music-1' },
              hints: [],
              verified: false
            }
          ]
        },
        {
          type: 'problem',
          id: 'problem-2',
          source_ref: 'Problem 2',
          prompt: '',
          parts: [
            {
              id: '2',
              label: '2',
              prompt: 'Solve "Produce a list of all members who have recommended another member" on pgexercises.',
              answer: { kind: 'external', platform: 'pgexercises', path: 'joins/self.html', title: 'Recommenders', number: null, slug: null },
              hints: [],
              verified: false
            }
          ]
        }
      ]
    }
  ]
} as unknown as Lesson

describe('a SQL chapter lesson', () => {
  let container: HTMLDivElement
  let reactRoot: Root
  const opened: string[] = []

  beforeEach(async () => {
    container = document.createElement('div')
    document.body.append(container)
    reactRoot = createRoot(container)
    window.kedami = { openPgExercises: async (path: string) => void opened.push(path) } as unknown as KedamiApi
    await act(async () =>
      reactRoot.render(
        <ProgressProvider lessonId="sql" initial={[]}>
          <OpenWorkspace.Provider value={() => {}}>
            <LessonView lesson={chapterLesson} />
          </OpenWorkspace.Provider>
        </ProgressProvider>
      )
    )
  })

  afterEach(async () => {
    await act(async () => reactRoot.unmount())
    container.remove()
  })

  it('credits the book in its header', () => {
    expect(container.querySelector('.lesson-header')!.textContent).toContain(CREDIT)
  })

  it('shows a bank problem with Solve and mark done, never as unverified', () => {
    const problem = card(container, 'Problem 1')
    expect([...problem.querySelectorAll('button')].map((b) => b.textContent)).toEqual(['Solve', 'Mark done'])
    expect(problem.textContent).not.toContain('Unverified answer')
  })

  it('opens a pgexercises problem on its site', async () => {
    const problem = card(container, 'Problem 2')
    expect(problem.textContent).toContain('Solve it on pgexercises, then mark it done.')
    const open = [...problem.querySelectorAll('button')].find((b) => b.textContent === 'Open on pgexercises')!
    await act(async () => open.click())
    expect(opened).toEqual(['joins/self.html'])
    expect(problem.textContent).not.toContain('Unverified answer')
  })
})

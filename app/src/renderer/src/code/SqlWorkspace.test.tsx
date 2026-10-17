import { EditorView } from '@codemirror/view'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import type { KedamiApi } from '../../../preload/api'
import type { ProgressRecord } from '../api'
import { ProgressProvider } from '../lesson/progress/ProgressContext'
import { type QueryTarget, SqlWorkspace } from './SqlWorkspace'

const TABLES = [
  { name: 'student', columns: ['id', 'name', 'year'], rows: [[1, 'Ada', 2], [2, 'Grace', null]], count: 25 },
  { name: 'enrolled', columns: ['student_id', 'course'], rows: [[1, 'CS101']], count: 1 }
]

const part: QueryTarget = {
  lessonId: 'l1',
  blockId: 'ps2-1',
  partId: 'a',
  title: 'PS2 #1',
  prompt: 'List the names of students in **year 3**.',
  answer: { kind: 'query', database: 'course/school', reference: 'SELECT name FROM student WHERE year = 3', ordered: false, exercise: null },
  hints: ['Filter on the year column.']
}

const practice: QueryTarget = {
  ...part,
  blockId: 'selecting-practice-1',
  partId: null,
  title: 'Practice',
  prompt: 'How many singers are there?',
  answer: { kind: 'query', database: 'bank/music', reference: 'SELECT count(*) FROM singer', ordered: false, exercise: 'music-1' },
  hints: []
}

let container: HTMLDivElement
let root: Root
let fetchMock: Mock
let replies: Record<string, (body: Record<string, unknown>) => Response>

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const record = (fields: Partial<ProgressRecord>): ProgressRecord => ({
  block_id: 'ps2-1', part_id: 'a', status: 'in_progress', last_response: null, attempts: 0, hints_used: 0, updated: null, ...fields
})

beforeEach(() => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  replies = {
    tables: () => json({ tables: TABLES }),
    'run-query': () => json({ columns: ['name'], rows: [['Grace'], ['Linus']], count: 2, truncated: false, error: null }),
    check: (body) =>
      json({
        correct: body.response === 'SELECT name FROM student WHERE year > 2',
        reason: body.response === 'SELECT name FROM student WHERE year > 2' ? null : 'Expected 2 rows, got 3.',
        progress: record({
          status: body.response === 'SELECT name FROM student WHERE year > 2' ? 'correct' : 'in_progress',
          last_response: body.response,
          attempts: 1
        }),
        result: { columns: ['name'], rows: [['Ada'], ['Grace'], ['Linus']], count: 3, truncated: false }
      }),
    code: (body) => json({ progress: record({ last_response: body.code }) }),
    hint: (body) => json({ progress: record({ hints_used: body.count as number }) })
  }
  fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    const path = new URL(url).pathname
    const route = path.slice(path.lastIndexOf('/') + 1)
    return replies[route](init.body ? JSON.parse(String(init.body)) : {})
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

async function mount(target: QueryTarget, records: ProgressRecord[] = []) {
  await act(async () =>
    root.render(
      <ProgressProvider lessonId="l1" initial={records}>
        <SqlWorkspace target={target} onBack={() => {}} />
      </ProgressProvider>
    )
  )
  await act(async () => {})
}

const calls = (route: string) =>
  fetchMock.mock.calls.filter(([url]) => new URL(url).pathname.endsWith(`/${route}`))
const bodies = (route: string) => calls(route).map(([, init]) => JSON.parse(init.body))
const button = (label: string) => [...container.querySelectorAll('button')].find((b) => b.textContent === label)
const click = (label: string) => act(async () => button(label)!.click())
const consoleText = () => container.querySelector('.console-output')!.textContent
const editor = () => EditorView.findFromDOM(container.querySelector<HTMLElement>('.cm-editor')!)!
const type = (text: string) =>
  act(async () => editor().dispatch({ changes: { from: 0, to: editor().state.doc.length, insert: text } }))

describe('the SQL workspace', () => {
  it("shows the question as Markdown and the database's tables, with counts and nulls", async () => {
    await mount(part)
    const description = container.querySelector('.workspace-description')!
    expect(description.querySelector('strong')!.textContent).toBe('year 3')
    const captions = [...description.querySelectorAll('.result-caption')].map((c) => c.textContent)
    expect(captions).toEqual(['student 25 rows', 'enrolled 1 row'])
    expect(description.textContent).toContain('23 more rows')
    expect(description.querySelector('td[data-null="true"]')!.textContent).toBe('NULL')
    expect(description.textContent).not.toContain('Spider')
    expect(new URL(calls('tables')[0][0]).search).toBe('?part_id=a')
  })

  it('has the Vim checkbox in its editor bar too', async () => {
    await mount(part)
    expect(container.querySelector('.workspace-editor .vim-control')!.textContent).toContain('Vim')
  })

  it('opens empty, or with the saved query', async () => {
    await mount(part)
    expect(editor().state.doc.toString()).toBe('')
    await act(async () => root.unmount())
    root = createRoot(container)
    await mount(part, [record({ last_response: 'SELECT name' })])
    expect(editor().state.doc.toString()).toBe('SELECT name')
  })

  it('credits Spider for a practice exercise, and asks for its tables without a part', async () => {
    await mount(practice)
    expect(container.querySelector('.workspace-description')!.textContent).toContain('From Spider (CC BY-SA 4.0)')
    expect(new URL(calls('tables')[0][0]).search).toBe('')
    expect(container.querySelector('.workspace-bar')!.textContent).toContain('Practice')
  })
})

describe('Run', () => {
  it('saves the query, runs it, and shows the result as a table without an attempt', async () => {
    await mount(part)
    await type('SELECT name FROM student WHERE year = 3')
    await click('Run')
    expect(bodies('code')).toEqual([{ part_id: 'a', code: 'SELECT name FROM student WHERE year = 3' }])
    expect(bodies('run-query')).toEqual([{ part_id: 'a', query: 'SELECT name FROM student WHERE year = 3' }])
    const cells = [...container.querySelectorAll('.console-output td')].map((c) => c.textContent)
    expect(cells).toEqual(['Grace', 'Linus'])
    expect(calls('check')).toEqual([])
  })

  it("shows why a query can't run", async () => {
    replies['run-query'] = () => json({ columns: [], rows: [], count: 0, truncated: false, error: 'no such column: nope' })
    await mount(part)
    await type('SELECT nope FROM student')
    await click('Run')
    expect(consoleText()).toContain('no such column: nope')
  })

  it('says how many more rows there are and when there were over 1,000', async () => {
    replies['run-query'] = () =>
      json({ columns: ['n'], rows: [[1], [2]], count: 1000, truncated: true, error: null })
    await mount(part)
    await click('Run')
    expect(consoleText()).toContain('More than 1,000 rows; the first 2 are shown.')
  })
})

describe('Submit', () => {
  it('says why a query is wrong and shows its result', async () => {
    await mount(part)
    await type('SELECT name FROM student')
    await click('Submit')
    expect(bodies('check')).toEqual([{ part_id: 'a', response: 'SELECT name FROM student' }])
    expect(consoleText()).toContain('Incorrect')
    expect(consoleText()).toContain('Expected 2 rows, got 3.')
    expect(container.querySelectorAll('.console-output td')).toHaveLength(3)
    expect(container.querySelector('.workspace-bar .state-label')!.textContent).toBe('In progress')
  })

  it('marks a right query correct, then takes no more submits but still runs', async () => {
    await mount(part)
    await type('SELECT name FROM student WHERE year > 2')
    await click('Submit')
    expect(consoleText()).toContain('Correct')
    expect(container.querySelector('.workspace-bar .state-label')!.textContent).toBe('Correct')
    expect(button('Submit')).toBeUndefined()
    expect(button('Run')).toBeDefined()
  })

  it("shows a query that can't run without counting it", async () => {
    replies.check = () => json({ detail: 'syntax error near "SELEC"' }, 422)
    await mount(part)
    await type('SELEC name')
    await click('Submit')
    expect(consoleText()).toContain('syntax error near "SELEC"')
    expect(container.querySelector('.workspace-bar .state-label')).toBeNull()
  })

  it('checks a practice checkpoint with no part', async () => {
    await mount(practice)
    await type('SELECT count(*) FROM singer')
    await click('Submit')
    expect(bodies('check')).toEqual([{ part_id: null, response: 'SELECT count(*) FROM singer' }])
  })
})

describe('saving and hints', () => {
  it('saves when typing stops for a second', async () => {
    vi.useFakeTimers()
    try {
      await mount(part)
      await type('SELECT 1')
      expect(calls('code')).toEqual([])
      await act(async () => vi.advanceTimersByTime(1000))
      expect(bodies('code')).toEqual([{ part_id: 'a', code: 'SELECT 1' }])
    } finally {
      vi.useRealTimers()
    }
  })

  it('reveals hints beside the question', async () => {
    await mount(part)
    await click('Show hint 1 of 1')
    expect(container.querySelector('.workspace-description .hints')!.textContent).toContain('Filter on the year column.')
  })
})

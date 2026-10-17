import { EditorView } from '@codemirror/view'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import type { KedamiApi } from '../../../preload/api'
import type { ProgressRecord, TestFlag } from '../api'
import { ProgressProvider } from '../lesson/progress/ProgressContext'
import type { CodeAnswer, Part, ProblemBlock } from '../lesson/types'
import type { RunRequest, RunResult, TestResult } from './harness'
import { CodeRunnerProvider } from './RunnerContext'
import type { CodeRunner } from './runner/client'
import { shownDescription, Workspace } from './Workspace'

const STARTER = 'class Solution:\n    def reverseList(self, head):\n        '
const answer: CodeAnswer = {
  kind: 'code',
  platform: 'leetcode',
  number: 206,
  title: 'Reverse Linked List',
  slug: 'reverse-linked-list',
  difficulty: 'Easy',
  method: 'reverseList',
  starter_code: STARTER,
  tests: [
    { args: 'head = list_node([1, 2])', expected: 'list_node([2, 1])', compare: 'same_list' },
    { args: 'head = list_node([])', expected: 'list_node([])', compare: 'same_list' },
    { args: 'head = list_node([7])', expected: 'list_node([7])', compare: 'same_list' },
    { args: 'head = list_node([1, 2, 3])', expected: 'list_node([3, 2, 1])', compare: 'same_list' }
  ]
}
const part = {
  id: '206',
  label: '206',
  prompt: 'Given the head of a singly linked list, reverse the list.\n\nNote: a * b and x_1 stay as written.',
  answer,
  hints: ['Keep track of the previous node.'],
  verified: false
} as Part & { answer: CodeAnswer }
const block = { type: 'problem', id: 'leetcode-206', source_ref: 'LeetCode #206', prompt: '', parts: [part] } as ProblemBlock

const pass = (got: string): TestResult => ({ passed: true, got, output: '', error: null })
const fail = (got: string): TestResult => ({ passed: false, got, output: '', error: null })

let container: HTMLDivElement
let root: Root
let fetchMock: Mock
let requests: RunRequest[]
let replies: RunResult[]
let ready: { resolve: () => void; reject: (error: Error) => void }

function fakeRunner(): CodeRunner {
  const promise = new Promise<void>((resolve, reject) => (ready = { resolve, reject }))
  promise.catch(() => {})
  return {
    ready: promise,
    run: async (request, onResult) => {
      requests.push(request)
      const result = replies.shift()!
      result.results.forEach((r) => onResult?.(r))
      return result
    },
    dispose: () => {}
  }
}

beforeEach(() => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  requests = []
  replies = []
  window.kedami = {
    serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }),
    openLeetCode: vi.fn(async () => {})
  } as unknown as KedamiApi
  fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body))
    const record = (fields: Partial<ProgressRecord>) => ({
      progress: { block_id: block.id, part_id: part.id, status: 'in_progress', last_response: body.code ?? null,
        attempts: 0, hints_used: 0, updated: null, ...fields }
    })
    const path = new URL(_url).pathname
    if (path.endsWith('/submit')) return json(record({ status: body.passed ? 'correct' : 'in_progress', attempts: 1 }))
    if (path.endsWith('/code')) return json(record({}))
    if (path.endsWith('/hint')) return json(record({ hints_used: body.count }))
    if (path.endsWith('/flags')) {
      const flags = body.action === 'flag' ? [{ block_id: block.id, part_id: part.id, ...body.test }] : []
      return json({ flags })
    }
    throw new Error(`unexpected request ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true
  }
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })
const calls = (suffix: string) =>
  fetchMock.mock.calls.filter(([url]) => new URL(url).pathname.endsWith(suffix)).map(([, init]) => JSON.parse(init.body))

async function mount(records: ProgressRecord[] = [], flags: TestFlag[] = []) {
  await act(async () =>
    root.render(
      <CodeRunnerProvider enabled mount={fakeRunner}>
        <ProgressProvider lessonId="l1" initial={records} initialFlags={flags}>
          <Workspace block={block} part={part} onBack={() => {}} />
        </ProgressProvider>
      </CodeRunnerProvider>
    )
  )
}

async function startPython() {
  await act(async () => ready.resolve())
}

const button = (label: string) =>
  [...container.querySelectorAll('button')].find((b) => b.textContent === label) as HTMLButtonElement | undefined
const click = (label: string) => act(async () => button(label)!.click())
const consoleText = () => container.querySelector('.console-output')!.textContent
const editor = () => EditorView.findFromDOM(container.querySelector<HTMLElement>('.cm-editor')!)!
const type = (text: string) =>
  act(async () => editor().dispatch({ changes: { from: editor().state.doc.length, insert: text } }))

describe('the workspace', () => {
  it('shows the problem, its description as written, and the starter code', async () => {
    await mount()
    expect(container.querySelector('.workspace-bar')!.textContent).toContain('LeetCode #206 Reverse Linked List')
    expect(container.querySelector('.workspace-bar')!.textContent).toContain('Easy')
    const description = container.querySelector('.problem-description')!
    expect(description.textContent).toBe(part.prompt)
    expect(shownDescription('Example 1:\n\n \n\u00a0\nInput: x\n\n\nOutput: y\n')).toBe('Example 1:\n\nInput: x\n\nOutput: y')
    expect(description.querySelector('em, strong')).toBeNull()
    expect(editor().state.doc.toString()).toBe(STARTER)
    expect(consoleText()).toBe('Run your code to see the results here.')
  })

  it('opens with the saved code when there is some', async () => {
    const saved = `${STARTER}return None\n`
    await mount([{ block_id: block.id, part_id: part.id, status: 'in_progress', last_response: saved, attempts: 0,
      hints_used: 0, updated: null }])
    expect(editor().state.doc.toString()).toBe(saved)
    expect(container.querySelector('.workspace-bar .state-label')!.textContent).toBe('In progress')
  })

  it('says Python is starting until the runner is ready, then offers Run and Submit', async () => {
    await mount()
    expect(container.querySelector('.workspace-actions')!.textContent).toBe('Starting Python')
    await startPython()
    expect(button('Run')!.disabled).toBe(false)
    expect(button('Submit')!.className).toContain('button-primary')
  })

  it("says why when Python can't start, and can't run", async () => {
    await mount()
    await act(async () => ready.reject(new Error('no wasm')))
    expect(consoleText()).toContain("Python couldn't start: no wasm")
    expect(button('Run')!.disabled).toBe(true)
  })
})

describe('Run', () => {
  it('tries the first three unflagged tests and shows each as LeetCode would', async () => {
    const flags = [{ block_id: block.id, part_id: part.id, args: answer.tests[1].args, expected: answer.tests[1].expected }]
    await mount([], flags)
    await startPython()
    replies.push({ error: null, output: '', results: [pass('[2, 1]'), fail('[]'), pass('[3, 2, 1]')] })
    await click('Run')
    expect(requests[0]).toEqual({
      code: STARTER,
      method: 'reverseList',
      tests: [answer.tests[0], answer.tests[2], answer.tests[3]],
      stopAtFailure: false
    })
    const cases = [...container.querySelectorAll('.console-case')]
    expect(cases.map((c) => c.getAttribute('data-state'))).toEqual(['correct', 'wrong', 'correct'])
    expect(cases[0].textContent).toContain('Test 1')
    expect(cases[1].textContent).toContain('Test 3')
    expect(cases[0].textContent).toContain('head = [1, 2]')
    expect(cases[0].textContent).not.toContain('list_node')
    expect(calls('/submit')).toEqual([])
  })

  it('saves changed code before it runs', async () => {
    await mount()
    await startPython()
    await type('return head')
    replies.push({ error: null, output: '', results: [] })
    await click('Run')
    expect(calls('/code')).toEqual([{ part_id: '206', code: `${STARTER}return head` }])
    expect(requests[0].code).toBe(`${STARTER}return head`)
  })

  it('shows an error raised before any test', async () => {
    await mount()
    await startPython()
    replies.push({ error: 'SyntaxError: invalid syntax', output: 'loading\n', results: [] })
    await click('Run')
    expect(consoleText()).toContain('SyntaxError: invalid syntax')
    expect(consoleText()).toContain('loading')
  })
})

describe('Submit', () => {
  it('runs every unflagged test, stopping at a failure, and records a pass', async () => {
    await mount()
    await startPython()
    replies.push({ error: null, output: '', results: answer.tests.map(() => pass('[]')) })
    await click('Submit')
    expect(requests[0].tests).toEqual(answer.tests)
    expect(requests[0].stopAtFailure).toBe(true)
    expect(calls('/submit')).toEqual([{ part_id: '206', code: STARTER, passed: true }])
    expect(consoleText()).toContain('All 4 tests passed.')
    expect(container.querySelector('.workspace-bar .state-label')!.textContent).toBe('Correct')
    // A correct part takes no more submits, but Run still works.
    expect(button('Submit')).toBeUndefined()
    expect(button('Run')).toBeDefined()
  })

  it('records a failure and shows the test it failed', async () => {
    await mount()
    await startPython()
    replies.push({ error: null, output: '', results: [pass('[2, 1]'), fail('[1]')] })
    await click('Submit')
    expect(calls('/submit')).toEqual([{ part_id: '206', code: STARTER, passed: false }])
    expect(consoleText()).toContain('Failed test 2 of 4')
    expect(consoleText()).toContain('[1]')
    expect(container.querySelector('.workspace-bar .state-label')!.textContent).toBe('In progress')
  })

  it('shows a timeout as the test that failed', async () => {
    await mount()
    await startPython()
    replies.push({ error: null, output: '', results: [{ passed: false, got: null, output: '', error: 'Time limit exceeded' }] })
    await click('Submit')
    expect(consoleText()).toContain('Failed test 1 of 4')
    expect(consoleText()).toContain('Time limit exceeded')
  })

  it("counts code that doesn't load as a failed Submit", async () => {
    await mount()
    await startPython()
    replies.push({ error: 'NameError: name x is not defined', output: '', results: [] })
    await click('Submit')
    expect(calls('/submit')).toEqual([{ part_id: '206', code: STARTER, passed: false }])
  })
})

describe('flags', () => {
  it('flags a failed test, skips it from then on, and clears flags', async () => {
    await mount()
    await startPython()
    replies.push({ error: null, output: '', results: [fail('[1, 2]')] })
    await click('Submit')
    await click('Flag as broken')
    expect(calls('/flags')).toEqual([
      { part_id: '206', action: 'flag', test: { args: answer.tests[0].args, expected: answer.tests[0].expected } }
    ])
    expect(container.querySelector('.workspace-console')!.textContent).toContain('1 test flagged')

    replies.push({ error: null, output: '', results: [] })
    await click('Submit')
    expect(requests[1].tests).toEqual(answer.tests.slice(1))

    await click('Clear flags')
    expect(calls('/flags').at(-1)).toEqual({ part_id: '206', action: 'clear' })
    expect(container.querySelector('.workspace-console')!.textContent).not.toContain('flagged')
  })
})

describe('saving', () => {
  it('saves when typing stops for a second', async () => {
    vi.useFakeTimers()
    try {
      await mount()
      await type('pass')
      expect(calls('/code')).toEqual([])
      await act(async () => vi.advanceTimersByTime(1000))
      expect(calls('/code')).toEqual([{ part_id: '206', code: `${STARTER}pass` }])
    } finally {
      vi.useRealTimers()
    }
  })

  it('saves unsaved code on leaving', async () => {
    await mount()
    await type('pass')
    await act(async () => root.unmount())
    expect(calls('/code')).toEqual([{ part_id: '206', code: `${STARTER}pass` }])
    root = createRoot(container)
  })

  it('resets to the starter code after a confirmation', async () => {
    const saved = `${STARTER}return None\n`
    await mount([{ block_id: block.id, part_id: part.id, status: 'in_progress', last_response: saved, attempts: 0,
      hints_used: 0, updated: null }])
    await click('Reset')
    expect(editor().state.doc.toString()).toBe(saved)
    await act(async () => container.querySelector<HTMLButtonElement>('dialog .button-primary')!.click())
    expect(editor().state.doc.toString()).toBe(STARTER)
  })
})

describe('hints', () => {
  it('reveals hints one at a time beside the description', async () => {
    await mount()
    await click('Show hint 1 of 1')
    expect(calls('/hint')).toEqual([{ part_id: '206', count: 1 }])
    expect(container.querySelector('.workspace-description .hints')!.textContent).toContain('Keep track of the previous node.')
    expect(button('Show hint 1 of 1')).toBeUndefined()
  })
})

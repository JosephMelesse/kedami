import { beforeEach, describe, expect, it } from 'vitest'
import type { RunRequest, RunResult, TestResult } from '../harness'
import { type CodeRunner, createRunner, TIME_LIMIT_EXCEEDED } from './client'
import type { FromFrame, ToFrame } from './protocol'

const request: RunRequest = { code: '', method: 'f', tests: [], stopAtFailure: true }
const passed: TestResult = { passed: true, got: '1', output: '', error: null }

let posted: { message: ToFrame; transfer?: Transferable[] }[]
let handler: ((message: FromFrame) => void) | null
let stopped: boolean
let runner: CodeRunner
let files: { wasm: ArrayBuffer; stdlib: ArrayBuffer }

const frame = (message: FromFrame): void => handler!(message)
const flush = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 0))
const runs = (): Extract<ToFrame, { type: 'run' }>[] =>
  posted.map((p) => p.message).filter((m): m is Extract<ToFrame, { type: 'run' }> => m.type === 'run')

beforeEach(() => {
  posted = []
  handler = null
  stopped = false
  files = { wasm: new ArrayBuffer(4), stdlib: new ArrayBuffer(2) }
  runner = createRunner(
    {
      post: (message, transfer) => posted.push({ message, transfer }),
      listen: (h) => {
        handler = h
        return () => {
          stopped = true
        }
      }
    },
    { frameSource: async () => 'the frame script', files: async () => files }
  )
})

async function ready(): Promise<void> {
  frame({ type: 'loaded' })
  await flush()
  frame({ type: 'ready' })
  await runner.ready
}

describe('loading', () => {
  it('sends the frame its script and the binaries, handing the binaries over', async () => {
    frame({ type: 'loaded' })
    await flush()
    expect(posted).toEqual([
      { message: { type: 'load', source: 'the frame script', files }, transfer: [files.wasm, files.stdlib] }
    ])
  })

  it('rejects ready, and every run, when Pyodide fails to start', async () => {
    frame({ type: 'loaded' })
    await flush()
    frame({ type: 'failed', message: 'no wasm' })
    await expect(runner.ready).rejects.toThrow('no wasm')
    await expect(runner.run(request)).rejects.toThrow('no wasm')
  })

  it('fails when the binaries cannot be read', async () => {
    const failing = createRunner(
      { post: () => {}, listen: (h) => ((handler = h), () => {}) },
      { frameSource: async () => '', files: () => Promise.reject(new Error('no file')) }
    )
    frame({ type: 'loaded' })
    await expect(failing.ready).rejects.toThrow('no file')
  })

  it('stops listening when disposed', () => {
    runner.dispose()
    expect(stopped).toBe(true)
  })
})

describe('running', () => {
  it('waits for the frame to be ready before posting a run', async () => {
    const result = runner.run(request)
    frame({ type: 'loaded' })
    await flush()
    expect(runs()).toEqual([])
    frame({ type: 'ready' })
    await flush()
    expect(runs()).toEqual([{ type: 'run', id: 1, request }])
    const done: RunResult = { error: null, output: '', results: [passed] }
    frame({ type: 'done', id: 1, result: done })
    await expect(result).resolves.toEqual(done)
  })

  it('reports each result as it arrives', async () => {
    await ready()
    const reported: TestResult[] = []
    const result = runner.run(request, (r) => reported.push(r))
    await flush()
    frame({ type: 'result', id: 1, result: passed })
    expect(reported).toEqual([passed])
    frame({ type: 'done', id: 1, result: { error: null, output: '', results: [passed] } })
    await result
  })

  it('takes one run at a time', async () => {
    await ready()
    const first = runner.run(request)
    await expect(runner.run(request)).rejects.toThrow('already running')
    await flush()
    frame({ type: 'done', id: 1, result: { error: null, output: '', results: [] } })
    await first
    const second = runner.run(request)
    await flush()
    expect(runs().map((r) => r.id)).toEqual([1, 2])
    frame({ type: 'done', id: 2, result: { error: null, output: '', results: [] } })
    await second
  })

  it('ignores messages for other runs', async () => {
    await ready()
    const reported: TestResult[] = []
    const result = runner.run(request, (r) => reported.push(r))
    await flush()
    frame({ type: 'result', id: 9, result: passed })
    frame({ type: 'done', id: 9, result: { error: 'wrong run', output: '', results: [] } })
    frame({ type: 'done', id: 1, result: { error: null, output: '', results: [] } })
    expect(reported).toEqual([])
    await expect(result).resolves.toMatchObject({ error: null })
  })
})

describe('malformed messages', () => {
  it('ignores results and run results that are not shaped like them', async () => {
    await ready()
    const reported: TestResult[] = []
    const result = runner.run(request, (r) => reported.push(r))
    await flush()
    frame({ type: 'result', id: 1, result: 'passed' as unknown as TestResult })
    frame({ type: 'result', id: 1, result: { ...passed, passed: 'yes' } as unknown as TestResult })
    frame({ type: 'done', id: 1, result: null as unknown as RunResult })
    frame({ type: 'done', id: 1, result: { error: null, output: '', results: [{}] } as unknown as RunResult })
    expect(reported).toEqual([])
    frame({ type: 'done', id: 1, result: { error: null, output: '', results: [passed] } })
    await expect(result).resolves.toEqual({ error: null, output: '', results: [passed] })
  })
})

describe('timeouts and crashes', () => {
  it('turns a timeout into the next test failing, and waits for the restarted worker', async () => {
    await ready()
    const reported: TestResult[] = []
    const first = runner.run(request, (r) => reported.push(r))
    await flush()
    frame({ type: 'result', id: 1, result: passed })
    frame({ type: 'timeout', id: 1 })
    const timedOut: TestResult = { passed: false, got: null, output: '', error: TIME_LIMIT_EXCEEDED }
    await expect(first).resolves.toEqual({ error: null, output: '', results: [passed, timedOut] })
    expect(reported).toEqual([passed, timedOut])

    const second = runner.run(request)
    await flush()
    expect(runs().map((r) => r.id)).toEqual([1])
    frame({ type: 'ready' })
    await flush()
    expect(runs().map((r) => r.id)).toEqual([1, 2])
    frame({ type: 'done', id: 2, result: { error: null, output: '', results: [] } })
    await second
  })

  it('turns a crash into the next test failing with its message', async () => {
    await ready()
    const result = runner.run(request)
    await flush()
    frame({ type: 'crashed', id: 1, message: 'out of memory' })
    await expect(result).resolves.toEqual({
      error: null,
      output: '',
      results: [{ passed: false, got: null, output: '', error: 'The runner stopped: out of memory' }]
    })
  })

  it('rejects a run in progress if the restarted worker fails to start', async () => {
    await ready()
    const first = runner.run(request)
    await flush()
    frame({ type: 'timeout', id: 1 })
    await first
    const second = runner.run(request)
    frame({ type: 'failed', message: 'no wasm' })
    await expect(second).rejects.toThrow('no wasm')
  })
})

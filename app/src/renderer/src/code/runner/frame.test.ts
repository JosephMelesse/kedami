import { beforeEach, describe, expect, it } from 'vitest'
import type { RunRequest, RunResult, TestResult } from '../harness'
import { createFrame, type Frame } from './frame'
import { type FromFrame, type FromWorker, TEST_LIMIT_MS, type ToWorker } from './protocol'

class FakeWorker {
  posted: ToWorker[] = []
  terminated = false
  constructor(
    readonly emit: (message: FromWorker) => void,
    readonly die: (message: string) => void
  ) {}
  postMessage(message: ToWorker): void {
    this.posted.push(message)
  }
  terminate(): void {
    this.terminated = true
  }
}

const files = { wasm: new ArrayBuffer(1), stdlib: new ArrayBuffer(1) }
const request: RunRequest = { code: '', method: 'f', tests: [], stopAtFailure: true }
const passed: TestResult = { passed: true, got: '1', output: '', error: null }
const done: RunResult = { error: null, output: '', results: [passed] }

let sent: FromFrame[]
let workers: FakeWorker[]
let now: number
let timers: { at: number; callback: () => void; cleared: boolean }[]
let frame: Frame

const worker = (): FakeWorker => workers[workers.length - 1]

function advance(ms: number): void {
  const until = now + ms
  for (;;) {
    const next = timers.filter((t) => !t.cleared && t.at <= until).sort((a, b) => a.at - b.at)[0]
    if (!next) break
    now = next.at
    next.cleared = true
    next.callback()
  }
  now = until
}

beforeEach(() => {
  sent = []
  workers = []
  now = 0
  timers = []
  frame = createFrame(files, {
    send: (message) => sent.push(message),
    createWorker: (onMessage, onError) => {
      const created = new FakeWorker(onMessage, onError)
      workers.push(created)
      return created
    },
    setTimer: (callback, ms) => {
      const timer = { at: now + ms, callback, cleared: false }
      timers.push(timer)
      return timer
    },
    clearTimer: (timer) => {
      ;(timer as { cleared: boolean }).cleared = true
    }
  })
})

function ready(): void {
  worker().emit({ type: 'ready' })
  sent = []
}

describe('starting', () => {
  it('starts a worker with the files and reports when it is ready', () => {
    expect(workers).toHaveLength(1)
    expect(worker().posted).toEqual([{ type: 'start', files }])
    worker().emit({ type: 'ready' })
    expect(sent).toEqual([{ type: 'ready' }])
  })

  it('reports a worker that fails to start, without restarting it', () => {
    worker().emit({ type: 'failed', message: 'no wasm' })
    expect(sent).toEqual([{ type: 'failed', message: 'no wasm' }])
    worker().die('again')
    expect(sent.at(-1)).toEqual({ type: 'failed', message: 'again' })
    expect(workers).toHaveLength(1)
  })

  it('ignores runs before the worker is ready', () => {
    frame.run(1, request)
    expect(worker().posted).toHaveLength(1)
  })
})

describe('running', () => {
  beforeEach(ready)

  it('relays a run and its results, then accepts the next', () => {
    frame.run(1, request)
    expect(worker().posted.at(-1)).toEqual({ type: 'run', id: 1, request })
    worker().emit({ type: 'result', id: 1, result: passed })
    worker().emit({ type: 'done', id: 1, result: done })
    expect(sent).toEqual([
      { type: 'result', id: 1, result: passed },
      { type: 'done', id: 1, result: done }
    ])
    frame.run(2, request)
    expect(worker().posted.at(-1)).toEqual({ type: 'run', id: 2, request })
  })

  it('ignores a second run while one is going', () => {
    frame.run(1, request)
    frame.run(2, request)
    expect(worker().posted.filter((m) => m.type === 'run')).toHaveLength(1)
  })

  it('ignores messages for any run but the current one', () => {
    frame.run(1, request)
    worker().emit({ type: 'result', id: 7, result: passed })
    worker().emit({ type: 'done', id: 7, result: done })
    expect(sent).toEqual([])
  })
})

describe('time limit', () => {
  beforeEach(ready)

  it('gives each test its own limit, restarting the clock at each result', () => {
    frame.run(1, request)
    for (let i = 0; i < 5; i++) {
      advance(TEST_LIMIT_MS - 1)
      worker().emit({ type: 'result', id: 1, result: passed })
    }
    advance(TEST_LIMIT_MS - 1)
    worker().emit({ type: 'done', id: 1, result: done })
    advance(TEST_LIMIT_MS * 3)
    expect(sent.map((m) => m.type)).toEqual(['result', 'result', 'result', 'result', 'result', 'done'])
    expect(workers).toHaveLength(1)
  })

  it('ends a test that runs past its limit, reports it, and starts a fresh worker', () => {
    frame.run(1, request)
    worker().emit({ type: 'result', id: 1, result: passed })
    advance(TEST_LIMIT_MS)
    expect(sent.at(-1)).toEqual({ type: 'timeout', id: 1 })
    expect(workers[0].terminated).toBe(true)
    expect(workers).toHaveLength(2)
    expect(worker().posted).toEqual([{ type: 'start', files }])
  })

  it('takes no run until the fresh worker is ready, then runs normally', () => {
    frame.run(1, request)
    advance(TEST_LIMIT_MS)
    frame.run(2, request)
    expect(worker().posted.filter((m) => m.type === 'run')).toEqual([])
    worker().emit({ type: 'ready' })
    frame.run(2, request)
    expect(worker().posted.at(-1)).toEqual({ type: 'run', id: 2, request })
  })

  it('ignores anything the ended worker still sends', () => {
    frame.run(1, request)
    advance(TEST_LIMIT_MS)
    const sentBefore = sent.length
    workers[0].emit({ type: 'done', id: 1, result: done })
    workers[0].emit({ type: 'ready' })
    workers[0].die('late')
    expect(sent).toHaveLength(sentBefore)
    expect(workers).toHaveLength(2)
  })

  it("doesn't time out between runs", () => {
    frame.run(1, request)
    worker().emit({ type: 'done', id: 1, result: done })
    advance(TEST_LIMIT_MS * 10)
    expect(sent.map((m) => m.type)).toEqual(['done'])
  })
})

describe('crashes', () => {
  beforeEach(ready)

  it('reports a worker that dies mid-run and starts a fresh one', () => {
    frame.run(1, request)
    worker().die('out of memory')
    expect(sent).toEqual([{ type: 'crashed', id: 1, message: 'out of memory' }])
    expect(workers[0].terminated).toBe(true)
    expect(workers).toHaveLength(2)
    advance(TEST_LIMIT_MS * 2)
    expect(sent).toHaveLength(1)
  })

  it('restarts a worker that dies while idle, saying nothing until it is ready', () => {
    worker().die('gone')
    expect(sent).toEqual([])
    expect(workers).toHaveLength(2)
    worker().emit({ type: 'ready' })
    expect(sent).toEqual([{ type: 'ready' }])
  })

  it('names a crash with no message', () => {
    frame.run(1, request)
    worker().die('')
    expect(sent).toEqual([{ type: 'crashed', id: 1, message: 'The runner stopped.' }])
  })
})

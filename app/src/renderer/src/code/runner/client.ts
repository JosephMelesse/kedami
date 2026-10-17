// The renderer's side of the code runner: one sandboxed frame, loaded with its script and Pyodide's
// binaries, taking one run at a time. A test that runs past its limit or kills the worker comes back
// as that test's failure. See architecture/code-problems.md, Runner.

import type { RunRequest, RunResult, TestResult } from '../harness'
import type { FromFrame, RuntimeFiles, ToFrame } from './protocol'

export const TIME_LIMIT_EXCEEDED = 'Time limit exceeded'

/** How the client talks to its frame, so tests can stand in for the real one. */
export interface FramePort {
  post(message: ToFrame, transfer?: Transferable[]): void
  listen(handler: (message: FromFrame) => void): () => void
}

export interface RunnerSources {
  /** The frame's script: frameEntry.ts, bundled with the worker. */
  frameSource(): Promise<string>
  files(): Promise<RuntimeFiles>
}

export interface CodeRunner {
  /** Resolves when the runner can take a run; rejects if Pyodide can't start. */
  readonly ready: Promise<void>
  /** Run a request, reporting each test's result as it finishes. One at a time. */
  run(request: RunRequest, onResult?: (result: TestResult) => void): Promise<RunResult>
  dispose(): void
}

type Running = {
  id: number
  results: TestResult[]
  onResult?: (result: TestResult) => void
  resolve: (result: RunResult) => void
  reject: (error: Error) => void
}

export function createRunner(port: FramePort, sources: RunnerSources): CodeRunner {
  let nextId = 1
  // True from when a run is asked for until it finishes, including while waiting for the frame.
  let busy = false
  let running: Running | null = null
  let failure: Error | null = null
  // A promise for the frame being ready to run, replaced each time its worker restarts.
  let idle = deferred()
  const firstReady = idle.promise

  const stop = port.listen((message) => {
    switch (message.type) {
      case 'loaded':
        Promise.all([sources.frameSource(), sources.files()]).then(
          ([source, files]) => port.post({ type: 'load', source, files }, [files.wasm, files.stdlib]),
          (error) => fail(String(error?.message ?? error))
        )
        return
      case 'ready':
        idle.resolve()
        return
      case 'failed':
        fail(message.message)
        return
      case 'result':
        if (running?.id !== message.id || !isTestResult(message.result)) return
        running.results.push(message.result)
        running.onResult?.(message.result)
        return
      case 'done':
        if (running?.id === message.id && isRunResult(message.result)) finish(message.result)
        return
      case 'timeout':
        if (running?.id === message.id) finishWithFailure(TIME_LIMIT_EXCEEDED)
        return
      case 'crashed':
        if (running?.id === message.id) finishWithFailure(`The runner stopped: ${message.message}`)
        return
    }
  })

  function finish(result: RunResult): void {
    const done = running!
    running = null
    busy = false
    done.resolve(result)
  }

  // The worker was ended mid-run and is restarting, so the next run waits for it.
  function finishWithFailure(error: string): void {
    const { results, onResult } = running!
    idle = deferred()
    const failed: TestResult = { passed: false, got: null, output: '', error }
    onResult?.(failed)
    finish({ error: null, output: '', results: [...results, failed] })
  }

  function fail(message: string): void {
    failure = new Error(message)
    idle.reject(failure)
    running?.reject(failure)
    running = null
    busy = false
  }

  firstReady.catch(() => {})

  return {
    ready: firstReady,
    async run(request, onResult) {
      if (failure) throw failure
      if (busy) throw new Error('The runner is already running.')
      busy = true
      try {
        await idle.promise
      } catch (error) {
        busy = false
        throw error
      }
      return new Promise<RunResult>((resolve, reject) => {
        running = { id: nextId++, results: [], onResult, resolve, reject }
        port.post({ type: 'run', id: running.id, request })
      })
    },
    dispose: stop
  }
}

// The student's code runs in the worker and could post anything, so results are checked before use.
function isTestResult(value: unknown): value is TestResult {
  const r = value as TestResult
  return (
    typeof r === 'object' &&
    r !== null &&
    typeof r.passed === 'boolean' &&
    (r.got === null || typeof r.got === 'string') &&
    typeof r.output === 'string' &&
    (r.error === null || typeof r.error === 'string')
  )
}

function isRunResult(value: unknown): value is RunResult {
  const r = value as RunResult
  return (
    typeof r === 'object' &&
    r !== null &&
    (r.error === null || typeof r.error === 'string') &&
    typeof r.output === 'string' &&
    Array.isArray(r.results) &&
    r.results.every(isTestResult)
  )
}

function deferred(): { promise: Promise<void>; resolve: () => void; reject: (error: Error) => void } {
  let resolve!: () => void
  let reject!: (error: Error) => void
  const promise = new Promise<void>((res, rej) => {
    resolve = res
    reject = rej
  })
  promise.catch(() => {})
  return { promise, resolve, reject }
}

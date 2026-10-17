// The runner frame's logic: keep one worker running Pyodide, relay runs to it, time each test, and end
// and restart the worker when a test runs past its limit or the worker dies. The worker and clock are
// passed in, so this runs the same in the frame and in tests.

import { type FromFrame, type FromWorker, type RuntimeFiles, TEST_LIMIT_MS, type ToWorker } from './protocol'
import type { RunRequest } from '../harness'

export interface WorkerLike {
  postMessage(message: ToWorker): void
  terminate(): void
}

export interface FrameDeps {
  send(message: FromFrame): void
  /** A new worker that calls back with each message it posts and if it dies. */
  createWorker(onMessage: (message: FromWorker) => void, onError: (message: string) => void): WorkerLike
  setTimer(callback: () => void, ms: number): unknown
  clearTimer(timer: unknown): void
}

export interface Frame {
  /** Start a run. Ignored unless the worker is ready and idle, which the renderer waits for. */
  run(id: number, request: RunRequest): void
}

export function createFrame(files: RuntimeFiles, deps: FrameDeps): Frame {
  let worker: WorkerLike
  let ready = false
  let running: number | null = null
  let timer: unknown = null

  function start(): void {
    ready = false
    // A worker that was ended can still have messages queued; only the current one's count.
    const current: WorkerLike = deps.createWorker(
      (message) => current === worker && fromWorker(message),
      (message) => current === worker && died(message || 'The runner stopped.')
    )
    worker = current
    current.postMessage({ type: 'start', files })
  }

  function fromWorker(message: FromWorker): void {
    switch (message.type) {
      case 'ready':
        ready = true
        deps.send({ type: 'ready' })
        return
      case 'failed':
        stopTimer()
        running = null
        deps.send({ type: 'failed', message: message.message })
        return
      case 'result':
        if (message.id !== running) return
        startTimer()
        deps.send(message)
        return
      case 'done':
        if (message.id !== running) return
        stopTimer()
        running = null
        deps.send(message)
        return
    }
  }

  function died(message: string): void {
    stopTimer()
    worker.terminate()
    if (running !== null) {
      deps.send({ type: 'crashed', id: running, message })
      running = null
    } else if (!ready) {
      // Dying before it was ever ready means Pyodide itself can't start, so restarting won't help.
      deps.send({ type: 'failed', message })
      return
    }
    start()
  }

  function timedOut(): void {
    const id = running
    if (id === null) return
    timer = null
    running = null
    worker.terminate()
    deps.send({ type: 'timeout', id })
    start()
  }

  function startTimer(): void {
    stopTimer()
    timer = deps.setTimer(timedOut, TEST_LIMIT_MS)
  }

  function stopTimer(): void {
    if (timer !== null) deps.clearTimer(timer)
    timer = null
  }

  start()
  return {
    run(id, request) {
      if (!ready || running !== null) return
      running = id
      startTimer()
      worker.postMessage({ type: 'run', id, request })
    }
  }
}

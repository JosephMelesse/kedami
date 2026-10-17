// Messages between the renderer, the runner frame, and the worker inside it.
// See architecture/code-problems.md, Runner.

import type { RunRequest, RunResult, TestResult } from '../harness'

/** Each test's limit, timed from when the previous test finished, or from when the run was posted. */
export const TEST_LIMIT_MS = 10_000

/** Pyodide's binaries, which the frame can't load itself, read by main from the installed package. */
export type RuntimeFiles = { wasm: ArrayBuffer; stdlib: ArrayBuffer }

/** Renderer to frame. The first message loads the frame's script; then runs, one at a time. */
export type ToFrame =
  | { type: 'load'; source: string; files: RuntimeFiles }
  | { type: 'run'; id: number; request: RunRequest }

/** Frame to renderer. */
export type FromFrame =
  /** The page is up and waiting for its script. */
  | { type: 'loaded' }
  | { type: 'ready' }
  /** Pyodide couldn't start; the runner is unusable. */
  | { type: 'failed'; message: string }
  | { type: 'result'; id: number; result: TestResult }
  | { type: 'done'; id: number; result: RunResult }
  /** The next test ran past its limit. The worker was ended and is restarting. */
  | { type: 'timeout'; id: number }
  /** The worker died mid-run, such as when Pyodide runs out of memory. It is restarting. */
  | { type: 'crashed'; id: number; message: string }

/** Frame to worker. */
export type ToWorker = { type: 'start'; files: RuntimeFiles } | { type: 'run'; id: number; request: RunRequest }

/** Worker to frame. */
export type FromWorker =
  | { type: 'ready' }
  | { type: 'failed'; message: string }
  | { type: 'result'; id: number; result: TestResult }
  | { type: 'done'; id: number; result: RunResult }

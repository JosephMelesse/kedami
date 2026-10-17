// The typed side of harness.py: what the runner sends it and what it returns.
// See architecture/code-problems.md, Runner.

import type { PyodideAPI } from 'pyodide'
import source from './harness.py?raw'
// LeetCode provides sortedcontainers, so the runner does too. This is PyPI's wheel, checked by its hash in the tests.
import sortedContainers from './vendor/sortedcontainers-2.4.0-py2.py3-none-any.whl?inline'

import type { CodeTest } from '../lesson/types'

export type { CodeTest }

export type RunRequest = {
  code: string
  method: string
  tests: CodeTest[]
  /** Submit stops at the first failure; Run tries every test it is given. */
  stopAtFailure: boolean
}

export type TestResult = {
  passed: boolean
  /** What the code returned, as Python shows it; null if it raised or the test can't be read. */
  got: string | null
  output: string
  error: string | null
}

export type RunResult = {
  /** An error before any test ran: the code doesn't compile, raises, or has no such method. */
  error: string | null
  /** Printed while the code itself was loading, before any test. */
  output: string
  /** One per test that ran, in order. */
  results: TestResult[]
}

export type Harness = (request: RunRequest, onResult?: (result: TestResult) => void) => RunResult

/** Installs the runner's packages into Pyodide, loads harness.py, and returns a function that runs one request. */
export function loadHarness(pyodide: PyodideAPI): Harness {
  // Decoded by hand rather than fetched: the runner frame's CSP allows no fetch, data URLs included.
  const base64 = sortedContainers.slice(sortedContainers.indexOf(',') + 1)
  pyodide.unpackArchive(Uint8Array.from(atob(base64), (c) => c.charCodeAt(0)), 'wheel')
  const harness = pyodide.runPython(`${source}\nrun_json`, { globals: pyodide.toPy({}) })
  return ({ code, method, tests, stopAtFailure }, onResult) => {
    const report = onResult && ((result: string) => onResult(JSON.parse(result)))
    return JSON.parse(harness(JSON.stringify({ code, method, tests, stop_at_failure: stopAtFailure }), report))
  }
}

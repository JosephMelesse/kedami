// The workspace console: the last Run or Submit, output only. See architecture/code-problems.md, Workspace.

import type { RunResult, TestResult } from './harness'
import { shownValue } from './tests'
import type { CodeTest } from '../lesson/types'

export type NumberedTest = { test: CodeTest; number: number }

export type ConsoleState =
  | { kind: 'idle' }
  | { kind: 'running'; mode: 'run' | 'submit'; done: number; total: number }
  | { kind: 'run'; result: RunResult; tests: NumberedTest[] }
  | { kind: 'submit'; result: RunResult; tests: NumberedTest[]; passed: boolean }
  /** The runner couldn't take the run, such as when Python failed to start. */
  | { kind: 'error'; message: string }

interface ConsoleProps {
  state: ConsoleState
  onFlag: (test: CodeTest) => void
}

export function ConsoleOutput({ state, onFlag }: ConsoleProps) {
  switch (state.kind) {
    case 'idle':
      return <p className="muted">Run your code to see the results here.</p>
    case 'running':
      return (
        <p className="muted" aria-live="polite">
          {state.mode === 'submit' ? `Passed ${state.done} of ${state.total}` : 'Running'}
        </p>
      )
    case 'error':
      return <p className="answer-error">{state.message}</p>
    case 'run':
      return (
        <>
          <LoadOutput result={state.result} />
          {state.result.results.map((result, i) => (
            <TestCase key={state.tests[i].number} title={`Test ${state.tests[i].number}`} test={state.tests[i].test}
              result={result} onFlag={onFlag} />
          ))}
        </>
      )
    case 'submit':
      return <SubmitOutput state={state} onFlag={onFlag} />
  }
}

type Submitted = Extract<ConsoleState, { kind: 'submit' }>

function SubmitOutput({ state, onFlag }: { state: Submitted; onFlag: ConsoleProps['onFlag'] }) {
  const total = state.tests.length
  if (state.passed) {
    return (
      <div className="console-case" data-state="correct">
        <span className="state-label state-label-correct">Accepted</span>
        <p>All {total} tests passed.</p>
      </div>
    )
  }
  const failedAt = state.result.results.findIndex((r) => !r.passed)
  return (
    <>
      <LoadOutput result={state.result} />
      {failedAt !== -1 && (
        <TestCase title={`Failed test ${failedAt + 1} of ${total}`} test={state.tests[failedAt].test}
          result={state.result.results[failedAt]} onFlag={onFlag} />
      )}
    </>
  )
}

/** What the code printed or raised while loading, before any test ran. */
function LoadOutput({ result }: { result: RunResult }) {
  if (!result.error && !result.output) return null
  return (
    <div className="console-case" data-state={result.error ? 'wrong' : undefined}>
      {result.error && <span className="state-label state-label-wrong">Error</span>}
      {result.output && <pre className="console-text">{result.output}</pre>}
      {result.error && <pre className="console-text">{result.error}</pre>}
    </div>
  )
}

interface TestCaseProps {
  title: string
  test: CodeTest
  result: TestResult
  onFlag: (test: CodeTest) => void
}

function TestCase({ title, test, result, onFlag }: TestCaseProps) {
  const state = result.passed ? 'correct' : 'wrong'
  return (
    <div className="console-case" data-state={state}>
      <div className="console-case-header">
        <span>{title}</span>
        <span className={`state-label state-label-${state}`}>{result.passed ? 'Passed' : 'Failed'}</span>
      </div>
      <dl className="console-values">
        <dt>Input</dt>
        <dd>
          <code>{shownValue(test.args) || '(none)'}</code>
        </dd>
        <dt>Expected</dt>
        <dd>
          <code>{shownValue(test.expected)}</code>
        </dd>
        {result.got !== null && (
          <>
            <dt>Output</dt>
            <dd>
              <code>{result.got}</code>
            </dd>
          </>
        )}
      </dl>
      {result.output && (
        <>
          <span className="muted">Printed</span>
          <pre className="console-text">{result.output}</pre>
        </>
      )}
      {result.error && <pre className="console-text">{result.error}</pre>}
      {!result.passed && (
        <button type="button" className="link-button" onClick={() => onFlag(test)}>
          Flag as broken
        </button>
      )}
    </div>
  )
}

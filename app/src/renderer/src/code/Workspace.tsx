// A LeetCode-style screen for one code problem: description on the left, editor and console on the right.
// See architecture/code-problems.md, Workspace, and the Workspace layout in architecture/ui.md.

import { createContext, useContext, useState } from 'react'
import { ConfirmDialog } from '../ConfirmDialog'
import { STATE_LABELS } from '../lesson/answers/AnswerField'
import { Hints } from '../lesson/answers/Hints'
import { useProgress } from '../lesson/progress/ProgressContext'
import { isDone, partState } from '../lesson/progress/state'
import type { CodeAnswer, CodeTest, Part, ProblemBlock } from '../lesson/types'
import { CodeEditor } from './CodeEditor'
import { ConsoleOutput, type ConsoleState, type NumberedTest } from './Console'
import { useCodeRunner } from './RunnerContext'
import { RUN_TESTS, submitPassed, unflagged } from './tests'
import { useAutosave } from './useAutosave'


/** LeetCode's text as scraped: where it had images, it has runs of blank lines. Shown with one at most. */
export function shownDescription(text: string): string {
  return text.replace(/\n(?:[ \t\u00a0]*\n){2,}/g, '\n\n').trim()
}

/** Opens the workspace for a code part, or a query part or checkpoint (partId null); null where there is
 * none, such as in tests of the lesson alone. */
export type OpenWorkspaceFn = (blockId: string, partId: string | null) => void
export const OpenWorkspace = createContext<OpenWorkspaceFn | null>(null)

export function useOpenWorkspace(): OpenWorkspaceFn | null {
  return useContext(OpenWorkspace)
}

interface WorkspaceProps {
  block: ProblemBlock
  part: Part & { answer: CodeAnswer }
  onBack: () => void
}

export function Workspace({ block, part, onBack }: WorkspaceProps) {
  const answer = part.answer
  const progress = useProgress()
  const { status, message, runner } = useCodeRunner()
  const record = progress.record(block.id, part.id)
  const state = partState(record)
  const done = isDone(state)
  const flags = progress.flags(block.id, part.id)
  const label = STATE_LABELS[state]

  const [code, setCode] = useState(() =>
    typeof record?.last_response === 'string' ? record.last_response : answer.starter_code
  )
  const [output, setOutput] = useState<ConsoleState>({ kind: 'idle' })
  const [error, setError] = useState<string | null>(null)
  const [resetting, setResetting] = useState(false)
  const running = output.kind === 'running'

  // Saved when typing stops, on Run and Submit, and on leaving with unsaved changes.
  const autosave = useAutosave(code, async (value) => {
    const failed = await progress.saveCode(block.id, part.id, value)
    if (failed) setError(failed)
  })

  const start = async (mode: 'run' | 'submit'): Promise<void> => {
    if (!runner || running) return
    setError(null)
    const all = unflagged(answer.tests, flags)
    const chosen: NumberedTest[] = mode === 'run' ? all.slice(0, RUN_TESTS) : all
    const submitted = code
    if (mode === 'run') await autosave.saveNow(submitted)
    setOutput({ kind: 'running', mode, done: 0, total: chosen.length })
    let result
    try {
      result = await runner.run(
        { code: submitted, method: answer.method, tests: chosen.map((t) => t.test), stopAtFailure: mode === 'submit' },
        (r) => setOutput((o) => (o.kind === 'running' && r.passed ? { ...o, done: o.done + 1 } : o))
      )
    } catch (err) {
      setOutput({ kind: 'error', message: `Python couldn't run the code: ${(err as Error).message}` })
      return
    }
    if (mode === 'run') {
      setOutput({ kind: 'run', result, tests: chosen })
      return
    }
    const passed = submitPassed(result, chosen.length)
    setOutput({ kind: 'submit', result, tests: chosen, passed })
    autosave.markSaved(submitted)
    setError(await progress.submit(block.id, part.id, submitted, passed))
  }

  const flag = async (test: CodeTest): Promise<void> => setError(await progress.flag(block.id, part.id, 'flag', test))
  const used = record?.hints_used ?? 0
  const reveal = async (): Promise<void> => setError(await progress.revealHint(block.id, part.id, used + 1))
  const starting = status === 'starting' || status === 'none'

  return (
    <section className="workspace fade-in" aria-label={`${block.source_ref} ${answer.title}`}>
      <nav className="workspace-bar">
        <button type="button" className="link-button" onClick={onBack}>
          Back to lesson
        </button>
        <span className="workspace-title">
          {block.source_ref} {answer.title}
        </span>
        <span className="muted">{answer.difficulty}</span>
        {label && <span className={`state-label state-label-${state}`}>{label}</span>}
      </nav>
      <div className="workspace-panes">
        <article className="workspace-pane workspace-description">
          <button
            type="button"
            className="link-button"
            onClick={() => window.kedami.openLeetCode(answer.slug).catch(() => setError('Could not open the browser.'))}
          >
            Open on LeetCode
          </button>
          <p className="problem-description">{shownDescription(part.prompt)}</p>
          <Hints hints={part.hints} used={used} />
          {!done && used < part.hints.length && (
            <button type="button" className="button" onClick={reveal}>
              Show hint {used + 1} of {part.hints.length}
            </button>
          )}
        </article>
        <div className="workspace-pane workspace-editor">
          <div className="workspace-pane-bar">
            <span className="muted">Python</span>
            <button type="button" className="link-button" onClick={() => setResetting(true)}>
              Reset
            </button>
          </div>
          <CodeEditor value={code} onChange={setCode} label={`Code for ${block.source_ref}`} />
        </div>
        <div className="workspace-pane workspace-console">
          <div className="console-output">
            {status === 'failed' ? (
              <p className="answer-error">Python couldn't start: {message}</p>
            ) : (
              <ConsoleOutput state={output} onFlag={flag} />
            )}
            {error && <p className="answer-error">{error}</p>}
          </div>
          <div className="workspace-pane-bar">
            {flags.length > 0 ? (
              <span className="muted">
                {flags.length === 1 ? '1 test flagged' : `${flags.length} tests flagged`}{' '}
                <button
                  type="button"
                  className="link-button"
                  onClick={() => progress.flag(block.id, part.id, 'clear').then(setError)}
                >
                  Clear flags
                </button>
              </span>
            ) : (
              <span />
            )}
            <div className="workspace-actions">
              {starting ? (
                <span className="muted">Starting Python</span>
              ) : (
                <>
                  <button type="button" className="button" disabled={!runner || running} onClick={() => start('run')}>
                    Run
                  </button>
                  {!done && (
                    <button type="button" className="button button-primary" disabled={!runner || running}
                      onClick={() => start('submit')}>
                      Submit
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
      {resetting && (
        <ConfirmDialog
          title="Reset to the starter code?"
          body="Your code for this problem will be replaced."
          confirmLabel="Reset"
          onCancel={() => setResetting(false)}
          onConfirm={() => {
            setResetting(false)
            setCode(answer.starter_code)
          }}
        />
      )}
    </section>
  )
}

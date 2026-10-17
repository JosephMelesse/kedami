// The workspace for a query part or checkpoint: its text and the database's tables on the left, a SQL editor
// on the right, and the console below it. See Workspace in architecture/sql-lessons.md.

import { useEffect, useState } from 'react'
import { getTables, type QueryResult, runQuery, type TableView } from '../api'
import { STATE_LABELS } from '../lesson/answers/AnswerField'
import { Hints } from '../lesson/answers/Hints'
import { Markdown } from '../lesson/Markdown'
import { useProgress } from '../lesson/progress/ProgressContext'
import { isDone, partState } from '../lesson/progress/state'
import type { QueryAnswer } from '../lesson/types'
import { CodeEditor } from './CodeEditor'
import { useAutosave } from './useAutosave'
import { useVimSetting } from './useVimSetting'
import { VimControl } from './VimControl'

/** What a query exercise needs, whether it is a problem part or a checkpoint (partId null). */
export interface QueryTarget {
  lessonId: string
  blockId: string
  partId: string | null
  /** How the top bar names it, such as "PS2 #1 (a)" or "Checkpoint". */
  title: string
  prompt: string
  answer: QueryAnswer
  hints: string[]
}

type Output =
  | { kind: 'idle' }
  | { kind: 'running' }
  | { kind: 'ran'; result: QueryResult }
  | { kind: 'checked'; correct: boolean; reason: string | null; result: QueryResult }
  | { kind: 'error'; message: string }

export function SqlWorkspace({ target, onBack }: { target: QueryTarget; onBack: () => void }) {
  const { lessonId, blockId, partId, answer } = target
  const progress = useProgress()
  const record = progress.record(blockId, partId)
  const state = partState(record)
  const done = isDone(state)
  const label = STATE_LABELS[state]

  const [query, setQuery] = useState(() => (typeof record?.last_response === 'string' ? record.last_response : ''))
  const [tables, setTables] = useState<TableView[] | null>(null)
  const [tablesError, setTablesError] = useState<string | null>(null)
  const [output, setOutput] = useState<Output>({ kind: 'idle' })
  const [error, setError] = useState<string | null>(null)
  const running = output.kind === 'running'
  const [vimOn, setVimOn] = useVimSetting()
  const [vimMode, setVimMode] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    getTables(lessonId, blockId, partId).then(
      (found) => current && setTables(found),
      (err: Error) => current && setTablesError(err.message)
    )
    return () => {
      current = false
    }
  }, [lessonId, blockId, partId])

  const autosave = useAutosave(query, async (value) => {
    const failed = await progress.saveCode(blockId, partId, value)
    if (failed) setError(failed)
  })

  const run = async (): Promise<void> => {
    if (running) return
    setError(null)
    await autosave.saveNow(query)
    setOutput({ kind: 'running' })
    try {
      const ran = await runQuery(lessonId, blockId, partId, query)
      setOutput(ran.error ? { kind: 'error', message: ran.error } : { kind: 'ran', result: ran })
    } catch (err) {
      setOutput({ kind: 'error', message: (err as Error).message })
    }
  }

  const submit = async (): Promise<void> => {
    if (running) return
    setError(null)
    setOutput({ kind: 'running' })
    autosave.markSaved(query)
    const checked = await progress.checkQuery(blockId, partId, query)
    setOutput(
      checked.error === null
        ? { kind: 'checked', correct: checked.correct, reason: checked.reason, result: checked.result }
        : { kind: 'error', message: checked.error }
    )
  }

  const used = record?.hints_used ?? 0
  const reveal = async (): Promise<void> => setError(await progress.revealHint(blockId, partId, used + 1))

  return (
    <section className="workspace fade-in" aria-label={target.title}>
      <nav className="workspace-bar">
        <button type="button" className="link-button" onClick={onBack}>
          Back to lesson
        </button>
        <span className="workspace-title">{target.title}</span>
        {label && <span className={`state-label state-label-${state}`}>{label}</span>}
      </nav>
      <div className="workspace-panes">
        <article className="workspace-pane workspace-description">
          <Markdown>{target.prompt}</Markdown>
          {tablesError && <p className="answer-error">{tablesError}</p>}
          {tables === null && !tablesError && <p className="muted">Loading the tables</p>}
          {tables?.map((table) => (
            <ResultTable
              key={table.name}
              caption={table.name}
              result={{ columns: table.columns, rows: table.rows, count: table.count, truncated: false }}
            />
          ))}
          <Hints hints={target.hints} used={used} />
          {!done && used < target.hints.length && (
            <button type="button" className="button" onClick={reveal}>
              Show hint {used + 1} of {target.hints.length}
            </button>
          )}
          {answer.exercise && <p className="muted">From Spider (CC BY-SA 4.0)</p>}
        </article>
        <div className="workspace-pane workspace-editor">
          <div className="workspace-pane-bar">
            <span className="editor-bar-start">
              <span className="muted">SQL</span>
              <VimControl on={vimOn} onChange={setVimOn} mode={vimMode} />
            </span>
          </div>
          <CodeEditor
            value={query}
            onChange={setQuery}
            label={`Query for ${target.title}`}
            language="sql"
            vimMode={vimOn}
            onVimMode={setVimMode}
            onSave={() => autosave.saveNow(query)}
          />
        </div>
        <div className="workspace-pane workspace-console">
          <div className="console-output">
            <QueryOutput output={output} />
            {error && <p className="answer-error">{error}</p>}
          </div>
          <div className="workspace-pane-bar">
            <span />
            <div className="workspace-actions">
              <button type="button" className="button" disabled={running} onClick={run}>
                Run
              </button>
              {!done && (
                <button type="button" className="button button-primary" disabled={running} onClick={submit}>
                  Submit
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function QueryOutput({ output }: { output: Output }) {
  switch (output.kind) {
    case 'idle':
      return <p className="muted">Run your query to see its result here.</p>
    case 'running':
      return <p className="muted">Running</p>
    case 'error':
      return (
        <div className="console-case" data-state="wrong">
          <span className="state-label state-label-wrong">Error</span>
          <pre className="console-text">{output.message}</pre>
        </div>
      )
    case 'ran':
      return <ResultTable result={output.result} />
    case 'checked':
      return (
        <div className="console-case" data-state={output.correct ? 'correct' : 'wrong'}>
          <span className={`state-label state-label-${output.correct ? 'correct' : 'wrong'}`}>
            {output.correct ? 'Correct' : 'Incorrect'}
          </span>
          {output.reason && <p>{output.reason}</p>}
          <ResultTable result={output.result} />
        </div>
      )
  }
}

/** A table of rows, with how many more there are beyond those shown. */
function ResultTable({ result, caption }: { result: QueryResult; caption?: string }) {
  const more = result.count - result.rows.length
  return (
    <div className="result-table">
      {caption && (
        <p className="result-caption">
          {caption} <span className="muted">{result.count === 1 ? '1 row' : `${result.count} rows`}</span>
        </p>
      )}
      <div className="result-scroll">
        <table>
          <thead>
            <tr>
              {result.columns.map((column, i) => (
                <th key={i}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, i) => (
              <tr key={i}>
                {row.map((value, j) => (
                  <td key={j} data-null={value === null}>
                    {value === null ? 'NULL' : String(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.truncated ? (
        <p className="muted">More than 1,000 rows; the first {result.rows.length} are shown.</p>
      ) : (
        more > 0 && <p className="muted">{more === 1 ? '1 more row' : `${more} more rows`}</p>
      )}
      {!caption && result.rows.length === 0 && <p className="muted">No rows.</p>}
    </div>
  )
}

// A query part or checkpoint in the lesson: its state, with Solve to open the SQL workspace. Its text shows
// above it as usual. See Workspace in architecture/sql-lessons.md.

import { useState } from 'react'
import { STATE_LABELS } from '../lesson/answers/AnswerField'
import { MarkDoneControl } from '../lesson/answers/MarkDoneControl'
import { useProgress } from '../lesson/progress/ProgressContext'
import { partState } from '../lesson/progress/state'
import type { QueryAnswer } from '../lesson/types'
import { useOpenWorkspace } from './Workspace'

interface QuerySummaryProps {
  blockId: string
  /** Null for a checkpoint, which can't be marked done. */
  partId: string | null
  answer: QueryAnswer
  verified: boolean
  name: string
}

export function QuerySummary({ blockId, partId, answer, verified, name }: QuerySummaryProps) {
  const progress = useProgress()
  const open = useOpenWorkspace()
  const state = partState(progress.record(blockId, partId))
  const label = STATE_LABELS[state]
  // A bank exercise's reference comes from the bank, so it is never called unverified.
  const showUnverified = !verified && answer.exercise === null
  const [error, setError] = useState<string | null>(null)

  return (
    <div className="answer-field" data-state={state}>
      {(label || showUnverified) && (
        <div className="answer-status">
          {label && <span className={`state-label state-label-${state}`}>{label}</span>}
          {showUnverified && <span className="status-label">Unverified answer</span>}
        </div>
      )}
      <div className="answer-footer">
        <div className="answer-actions">
          {open && (
            <button type="button" className="button button-primary" onClick={() => open(blockId, partId)}>
              Solve
            </button>
          )}
        </div>
        {partId !== null && (
          <MarkDoneControl
            name={name}
            state={state}
            onChange={async (done) => setError(await progress.markDone(blockId, partId, done))}
          />
        )}
      </div>
      {error && <p className="answer-error">{error}</p>}
    </div>
  )
}

import { useState } from 'react'
import { useProgress } from '../progress/ProgressContext'
import { isDone, type PartState, partState } from '../progress/state'
import type { Answer } from '../types'
import { AnswerInput } from './AnswerInput'
import { Hints } from './Hints'
import { MarkDoneControl } from './MarkDoneControl'

// State labels and borders from the part states table in completion-and-verification.md.
const STATE_LABELS: Record<PartState, string | null> = {
  not_started: null,
  in_progress: 'In progress',
  wrong: 'In progress',
  correct: 'Correct',
  marked_done: 'Marked done'
}

interface AnswerFieldProps {
  blockId: string
  /** Null for a checkpoint. */
  partId: string | null
  /** How the mark done confirmation names this part, such as "PS3 #4 (b)". */
  name: string
  answer: Answer
  hints: string[]
  verified: boolean
}

export function AnswerField({ blockId, partId, name, answer, hints, verified }: AnswerFieldProps) {
  const progress = useProgress()
  const record = progress.record(blockId, partId)
  const state = partState(record)
  const done = isDone(state)
  const used = record?.hints_used ?? 0
  const canHint = !done && used < hints.length
  const canMark = partId !== null && state !== 'correct'
  const [error, setError] = useState<string | null>(null)

  // Self checks and problems solved elsewhere are never verified, so they never show the label.
  const showUnverified = !verified && answer.kind !== 'self_check' && answer.kind !== 'external'
  const label = STATE_LABELS[state]

  const submit = async (response: unknown) => setError(await progress.check(blockId, partId, response))
  const reveal = async (count: number) => setError(await progress.revealHint(blockId, partId, count))
  const mark = async (value: boolean) => {
    if (partId !== null) setError(await progress.markDone(blockId, partId, value))
  }

  return (
    <div className="answer-field" data-state={state}>
      {(label || showUnverified) && (
        <div className="answer-status">
          {label && <span className={`state-label state-label-${state}`}>{label}</span>}
          {showUnverified && <span className="status-label">Unverified answer</span>}
        </div>
      )}
      <AnswerInput answer={answer} initial={record?.last_response ?? null} locked={done} onSubmit={submit} />
      {error && <p className="answer-error">{error}</p>}
      <Hints hints={hints} used={used} />
      {(canHint || canMark) && (
        <div className="answer-footer">
          {canHint ? (
            <button type="button" className="button" onClick={() => reveal(used + 1)}>
              Show hint {used + 1} of {hints.length}
            </button>
          ) : (
            <span />
          )}
          {canMark && <MarkDoneControl name={name} state={state} onChange={mark} />}
        </div>
      )}
    </div>
  )
}

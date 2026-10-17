// A code problem in the lesson: its title, difficulty, and state, with Solve to open its workspace.
// The description shows only in the workspace. See architecture/code-problems.md, In a lesson.

import { useState } from 'react'
import { STATE_LABELS } from '../lesson/answers/AnswerField'
import { MarkDoneControl } from '../lesson/answers/MarkDoneControl'
import { useProgress } from '../lesson/progress/ProgressContext'
import { partState } from '../lesson/progress/state'
import type { CodeAnswer, Part, ProblemBlock } from '../lesson/types'
import { useOpenWorkspace } from './Workspace'

interface CodeProblemSummaryProps {
  block: ProblemBlock
  part: Part
  answer: CodeAnswer
  name: string
}

export function CodeProblemSummary({ block, part, answer, name }: CodeProblemSummaryProps) {
  const progress = useProgress()
  const open = useOpenWorkspace()
  const state = partState(progress.record(block.id, part.id))
  const label = STATE_LABELS[state]
  const [error, setError] = useState<string | null>(null)

  return (
    <div className="answer-field" data-state={state}>
      <div className="code-problem">
        <span className="code-problem-title">{answer.title}</span>
        <span className="muted">{answer.difficulty}</span>
        {label && <span className={`state-label state-label-${state}`}>{label}</span>}
      </div>
      <div className="answer-footer">
        <div className="answer-actions">
          {open && (
            <button type="button" className="button button-primary" onClick={() => open(block.id, part.id)}>
              Solve
            </button>
          )}
          <button
            type="button"
            className="link-button"
            onClick={() => window.kedami.openLeetCode(answer.slug).catch(() => setError('Could not open the browser.'))}
          >
            Open on LeetCode
          </button>
        </div>
        <MarkDoneControl
          name={name}
          state={state}
          onChange={async (done) => setError(await progress.markDone(block.id, part.id, done))}
        />
      </div>
      {error && <p className="answer-error">{error}</p>}
    </div>
  )
}

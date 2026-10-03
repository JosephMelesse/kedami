import type { Answer } from '../types'
import { AnswerInput } from './AnswerInput'

// The box around an answer. Part states (build step 2) color its border and add a label.
export function AnswerField({ answer, verified }: { answer: Answer; verified: boolean }) {
  // self_check answers are never verified, so they never show the label.
  const showUnverified = !verified && answer.kind !== 'self_check'

  return (
    <div className="answer-field">
      {showUnverified && (
        <div className="answer-status">
          <span className="status-label">Unverified answer</span>
        </div>
      )}
      <AnswerInput answer={answer} />
    </div>
  )
}

import type { LessonStatus, LessonSummary } from '../api'
import { ProgressBar } from '../ProgressBar'

const SUBJECTS: Record<LessonSummary['subject'], string> = { math: 'Math', physics: 'Physics' }
const STATUS_LABELS: Record<LessonStatus, string> = { generating: 'Generating', ready: 'Ready', failed: 'Generation failed' }

export function LessonTile({ lesson, onOpen }: { lesson: LessonSummary; onOpen: () => void }) {
  const ready = lesson.status === 'ready'
  return (
    <button type="button" className="tile" onClick={onOpen} disabled={!ready}>
      <span className="eyebrow">{SUBJECTS[lesson.subject]}</span>
      <span className="tile-title">{lesson.title}</span>
      {ready ? (
        <span className="tile-progress">
          <ProgressBar done={lesson.problems_done} total={lesson.problems_total} />
          <span className="muted">
            {lesson.problems_done} of {lesson.problems_total} problems done
          </span>
        </span>
      ) : (
        <span className="muted">{STATUS_LABELS[lesson.status]}</span>
      )}
    </button>
  )
}

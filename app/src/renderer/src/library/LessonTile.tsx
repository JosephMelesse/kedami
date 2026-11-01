import type { LessonStatus, LessonSummary } from '../api'
import { ProgressBar } from '../ProgressBar'
import { SUBJECT_LABELS } from '../subjects'
import { DueLabel } from './DueLabel'

const STATUS_LABELS: Record<LessonStatus, string> = {
  placeholder: 'Not generated',
  generating: 'Generating',
  ready: 'Ready',
  failed: 'Generation failed'
}

export function LessonTile({ lesson, onOpen }: { lesson: LessonSummary; onOpen: () => void }) {
  const ready = lesson.status === 'ready'
  return (
    <button type="button" className={lesson.overdue ? 'tile tile-overdue' : 'tile'} onClick={onOpen}>
      <span className="eyebrow">{lesson.subject ? SUBJECT_LABELS[lesson.subject] : 'Placeholder'}</span>
      <span className="tile-title">{lesson.title}</span>
      <DueLabel date={lesson.due_date} overdue={lesson.overdue} />
      {ready ? (
        <span className="tile-progress">
          <ProgressBar done={lesson.problems_done} total={lesson.problems_total} />
          <span className="muted">
            {lesson.problems_done} of {lesson.problems_total} problems done
          </span>
        </span>
      ) : (
        <span className="muted tile-footer">{STATUS_LABELS[lesson.status]}</span>
      )}
    </button>
  )
}

import { useRef } from 'react'
import { ProgressBar } from '../ProgressBar'
import { SUBJECT_LABELS } from '../subjects'
import { useProgress } from './progress/ProgressContext'
import { problemCounts } from './progress/state'
import { useReadingPosition } from './reading/useReadingPosition'
import { SectionView } from './SectionView'
import type { Lesson } from './types'


export function LessonView({ lesson, readingBlock = null }: { lesson: Lesson; readingBlock?: string | null }) {
  const progress = useProgress()
  const { done, total } = problemCounts(lesson, progress.map)
  const article = useRef<HTMLElement>(null)
  useReadingPosition(lesson.id, readingBlock, article)

  return (
    <article className="lesson" ref={article}>
      <header className="lesson-header">
        <span className="eyebrow">{SUBJECT_LABELS[lesson.subject]}</span>
        <h1>{lesson.title}</h1>
        {lesson.source_files.length > 0 && <p className="muted">From {lesson.source_files.join(', ')}</p>}
        <div className="lesson-progress">
          <ProgressBar done={done} total={total} />
          <span className="muted">{done === total && total > 0 ? 'Lesson complete' : `${done} of ${total} problems done`}</span>
        </div>
      </header>
      {lesson.sections.map((section) => (
        <SectionView key={section.id} section={section} lessonId={lesson.id} />
      ))}
    </article>
  )
}

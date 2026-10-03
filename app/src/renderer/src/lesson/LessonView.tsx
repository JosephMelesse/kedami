import { ProgressBar } from '../ProgressBar'
import { useProgress } from './progress/ProgressContext'
import { problemCounts } from './progress/state'
import { SectionView } from './SectionView'
import type { Lesson } from './types'

const SUBJECTS: Record<Lesson['subject'], string> = { math: 'Math', physics: 'Physics' }

export function LessonView({ lesson }: { lesson: Lesson }) {
  const progress = useProgress()
  const { done, total } = problemCounts(lesson, progress.map)

  return (
    <article className="lesson">
      <header className="lesson-header">
        <span className="eyebrow">{SUBJECTS[lesson.subject]}</span>
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

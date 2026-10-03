import { SectionView } from './SectionView'
import type { Lesson } from './types'

const SUBJECTS: Record<Lesson['subject'], string> = { math: 'Math', physics: 'Physics' }

export function LessonView({ lesson }: { lesson: Lesson }) {
  return (
    <article className="lesson">
      <header className="lesson-header">
        <span className="eyebrow">{SUBJECTS[lesson.subject]}</span>
        <h1>{lesson.title}</h1>
        {lesson.source_files.length > 0 && <p className="muted">From {lesson.source_files.join(', ')}</p>}
      </header>
      {lesson.sections.map((section) => (
        <SectionView key={section.id} section={section} lessonId={lesson.id} />
      ))}
    </article>
  )
}

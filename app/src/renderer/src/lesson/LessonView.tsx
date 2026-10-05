import { Fragment, useMemo, useRef } from 'react'
import { ProgressBar } from '../ProgressBar'
import { SUBJECT_LABELS } from '../subjects'
import { useProgress } from './progress/ProgressContext'
import { problemCounts } from './progress/state'
import { FinishLine } from './days/FinishLine'
import { useFinishLines } from './days/useFinishLines'
import { useReadingPosition } from './reading/useReadingPosition'
import { SectionView } from './SectionView'
import type { Lesson } from './types'

const NO_DAYS: string[] = []

interface LessonViewProps {
  lesson: Lesson
  readingBlock?: string | null
  /** The blocks that begin day 2 onward. */
  dayStarts?: string[]
}

export function LessonView({ lesson, readingBlock = null, dayStarts = NO_DAYS }: LessonViewProps) {
  const progress = useProgress()
  const { done, total } = problemCounts(lesson, progress.map)
  const article = useRef<HTMLElement>(null)
  const opened = useReadingPosition(lesson.id, readingBlock, article)
  useFinishLines(article, dayStarts, opened)
  // The day each finish line ends, by the block that follows it.
  const lineBefore = useMemo(() => new Map(dayStarts.map((blockId, index) => [blockId, index + 1])), [dayStarts])

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
      {lesson.sections.map((section) => {
        // A line before a section's first block goes above its heading.
        const day = lineBefore.get(section.blocks[0]?.id)
        return (
          <Fragment key={section.id}>
            {day && <FinishLine day={day} />}
            <SectionView section={section} lessonId={lesson.id} lineBefore={lineBefore} />
          </Fragment>
        )
      })}
    </article>
  )
}

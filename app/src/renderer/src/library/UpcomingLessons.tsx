import type { Folder, LessonSummary } from '../api'
import { DueLabel } from './DueLabel'
import { folderPath } from './folders'

interface UpcomingProps {
  lessons: LessonSummary[]
  folders: Folder[]
  onOpen: (lesson: LessonSummary) => void
}

/**
 * The home page's card of unfinished lessons with due dates, soonest first. Overdue lessons have the earliest
 * dates, so they come first. See Deadlines in architecture/ui.md.
 */
export function UpcomingLessons({ lessons, folders, onOpen }: UpcomingProps) {
  const upcoming = lessons
    .filter((lesson) => lesson.due_date !== null && !lesson.done)
    .sort(
      (a, b) =>
        a.due_date!.localeCompare(b.due_date!) || a.created.localeCompare(b.created) || a.id.localeCompare(b.id)
    )
  if (upcoming.length === 0) return null
  return (
    <section className="upcoming-lessons" aria-labelledby="upcoming-heading">
      <h2 id="upcoming-heading">Upcoming</h2>
      <ul className="active-rows">
        {upcoming.map((lesson) => {
          const folder = folders.find((f) => f.id === lesson.folder_id)
          return (
            <li key={lesson.id}>
              <button type="button" className="active-row upcoming-row" onClick={() => onOpen(lesson)}>
                <span className="active-title">{lesson.title}</span>
                <span className="muted upcoming-path">{folder ? folderPath(folders, folder) : ''}</span>
                <DueLabel date={lesson.due_date} overdue={lesson.overdue} />
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

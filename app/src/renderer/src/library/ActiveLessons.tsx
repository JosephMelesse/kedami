import type { LessonSummary } from '../api'

/** The home page's card of active lessons, a row each with a box per problem. See Active lessons in architecture/ui.md. */
export function ActiveLessons({ lessons, onOpen }: { lessons: LessonSummary[]; onOpen: (lesson: LessonSummary) => void }) {
  const active = lessons.filter((lesson) => lesson.active)
  if (active.length === 0) return null
  return (
    <section className="active-lessons" aria-labelledby="active-heading">
      <h2 id="active-heading">Active</h2>
      <ul className="active-rows">
        {active.map((lesson) => (
          <li key={lesson.id}>
            <button type="button" className="active-row" onClick={() => onOpen(lesson)}>
              <span className="active-title">{lesson.title}</span>
              {lesson.status === 'ready' ? (
                <ProblemsLeft done={lesson.problems_done} total={lesson.problems_total} />
              ) : (
                <span className="muted">Generating</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function ProblemsLeft({ done, total }: { done: number; total: number }) {
  const left = total - done
  return (
    <>
      <span className="problem-boxes" role="img" aria-label={`${done} of ${total} problems done`}>
        {Array.from({ length: total }, (_, index) => (
          <span key={index} className={index < done ? 'problem-box problem-box-done' : 'problem-box'} />
        ))}
      </span>
      <span className="muted active-left">
        {left === 0 ? 'All problems done' : `${left} ${left === 1 ? 'problem' : 'problems'} left`}
      </span>
    </>
  )
}

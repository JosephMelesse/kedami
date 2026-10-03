import { useEffect, useState } from 'react'
import { type LessonSummary, listLessons } from '../api'
import { LessonTile } from './LessonTile'
import { NewLessonTile } from './NewLessonTile'

type State = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; lessons: LessonSummary[] }

export function LibraryScreen({ onOpen }: { onOpen: (lessonId: string) => void }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    listLessons()
      .then((lessons) => !cancelled && setState({ status: 'ready', lessons }))
      .catch((error: Error) => !cancelled && setState({ status: 'error', message: error.message }))
    return () => {
      cancelled = true
    }
  }, [])

  if (state.status === 'loading') return <p className="screen-message">Loading lessons</p>
  if (state.status === 'error') return <p className="screen-message">Could not load lessons: {state.message}</p>
  return <LibraryView lessons={state.lessons} onOpen={onOpen} />
}

export function LibraryView({ lessons, onOpen }: { lessons: LessonSummary[]; onOpen: (lessonId: string) => void }) {
  return (
    <div className="library">
      <h1>Lessons</h1>
      <ul className="tile-grid">
        {lessons.map((lesson) => (
          <li key={lesson.id}>
            <LessonTile lesson={lesson} onOpen={() => onOpen(lesson.id)} />
          </li>
        ))}
        <li>
          <NewLessonTile />
        </li>
      </ul>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { type LessonSummary, listLessons } from '../api'
import { LessonTile } from './LessonTile'
import { NewLessonTile } from './NewLessonTile'

type State = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; lessons: LessonSummary[] }

const POLL_MS = 3000

interface LibraryProps {
  onOpen: (lesson: LessonSummary) => void
  onNew: () => void
}

export function LibraryScreen({ onOpen, onNew }: LibraryProps) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const generating = state.status === 'ready' && state.lessons.some((lesson) => lesson.status === 'generating')

  useEffect(() => {
    let cancelled = false
    const load = () =>
      listLessons()
        .then((lessons) => !cancelled && setState({ status: 'ready', lessons }))
        .catch((error: Error) => !cancelled && setState({ status: 'error', message: error.message }))
    load()
    // Refresh while a lesson is generating, so its tile shows when it is ready.
    const timer = generating ? setInterval(load, POLL_MS) : undefined
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [generating])

  if (state.status === 'loading') return <p className="screen-message">Loading lessons</p>
  if (state.status === 'error') return <p className="screen-message">Could not load lessons: {state.message}</p>
  return <LibraryView lessons={state.lessons} onOpen={onOpen} onNew={onNew} />
}

export function LibraryView({ lessons, onOpen, onNew }: LibraryProps & { lessons: LessonSummary[] }) {
  return (
    <div className="library">
      <h1>Lessons</h1>
      <ul className="tile-grid">
        {lessons.map((lesson) => (
          <li key={lesson.id}>
            <LessonTile lesson={lesson} onOpen={() => onOpen(lesson)} />
          </li>
        ))}
        <li>
          <NewLessonTile onClick={onNew} />
        </li>
      </ul>
    </div>
  )
}

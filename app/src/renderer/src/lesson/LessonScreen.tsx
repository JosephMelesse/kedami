import { useEffect, useState } from 'react'
import { getLesson } from '../api'
import { LessonView } from './LessonView'
import type { Lesson } from './types'

type State = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; lesson: Lesson }

export function LessonScreen({ lessonId }: { lessonId: string }) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    getLesson(lessonId)
      .then((body) => !cancelled && setState({ status: 'ready', lesson: body.lesson }))
      .catch((error: Error) => !cancelled && setState({ status: 'error', message: error.message }))
    return () => {
      cancelled = true
    }
  }, [lessonId])

  if (state.status === 'loading') return <p className="screen-message">Loading lesson</p>
  if (state.status === 'error') return <p className="screen-message">Could not load the lesson: {state.message}</p>
  return <LessonView lesson={state.lesson} />
}

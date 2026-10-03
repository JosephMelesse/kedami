import { useEffect, useState } from 'react'
import { getLesson } from '../api'
import { LessonView } from './LessonView'
import type { Lesson } from './types'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'unavailable'; message: string }
  | { status: 'ready'; lesson: Lesson }

const UNAVAILABLE = {
  generating: 'This lesson is still being generated.',
  failed: 'This lesson failed to generate.'
}

interface LessonScreenProps {
  lessonId: string
  onBack: () => void
}

export function LessonScreen({ lessonId, onBack }: LessonScreenProps) {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    getLesson(lessonId)
      .then((body) => {
        if (cancelled) return
        if (body.status === 'ready' && body.lesson) setState({ status: 'ready', lesson: body.lesson })
        else setState({ status: 'unavailable', message: UNAVAILABLE[body.status === 'failed' ? 'failed' : 'generating'] })
      })
      .catch((error: Error) => !cancelled && setState({ status: 'error', message: error.message }))
    return () => {
      cancelled = true
    }
  }, [lessonId])

  return (
    <>
      <nav className="screen-nav">
        <button type="button" className="link-button" onClick={onBack}>
          Library
        </button>
      </nav>
      {state.status === 'loading' && <p className="screen-message">Loading lesson</p>}
      {state.status === 'error' && <p className="screen-message">Could not load the lesson: {state.message}</p>}
      {state.status === 'unavailable' && <p className="screen-message">{state.message}</p>}
      {state.status === 'ready' && <LessonView lesson={state.lesson} />}
    </>
  )
}

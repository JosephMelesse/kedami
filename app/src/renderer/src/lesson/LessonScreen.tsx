import { useEffect, useState } from 'react'
import { getLesson, getProgress, type ProgressRecord } from '../api'
import { LessonView } from './LessonView'
import { ProgressProvider } from './progress/ProgressContext'
import type { Lesson } from './types'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'unavailable'; message: string }
  | { status: 'ready'; lesson: Lesson; progress: ProgressRecord[] }

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
    load(lessonId)
      .then((next) => !cancelled && setState(next))
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
      {state.status === 'ready' && (
        <ProgressProvider key={lessonId} lessonId={lessonId} initial={state.progress}>
          <LessonView lesson={state.lesson} />
        </ProgressProvider>
      )}
    </>
  )
}

async function load(lessonId: string): Promise<State> {
  const body = await getLesson(lessonId)
  if (body.status !== 'ready' || !body.lesson) {
    return { status: 'unavailable', message: UNAVAILABLE[body.status === 'failed' ? 'failed' : 'generating'] }
  }
  return { status: 'ready', lesson: body.lesson, progress: await getProgress(lessonId) }
}

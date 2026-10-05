import { useEffect, useState } from 'react'
import { ApiError, getLesson, getProgress, type LessonResponse, type ProgressRecord, saveDays } from '../api'
import { RerunDialog } from '../generating/RerunDialog'
import { boundaries, lessonEnd, MAX_DAYS, splitDays } from './days/days'
import { DaysDialog } from './days/DaysDialog'
import { LessonView } from './LessonView'
import { ProgressProvider } from './progress/ProgressContext'
import type { Lesson } from './types'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'unavailable'; message: string }
  | { status: 'ready'; lesson: Lesson; progress: ProgressRecord[]; response: LessonResponse }

const UNAVAILABLE = {
  generating: 'This lesson is still being generated.',
  failed: 'This lesson failed to generate.'
}

interface LessonScreenProps {
  lessonId: string
  onBack: () => void
  onRerun: (lessonId: string) => void
}

export function LessonScreen({ lessonId, onBack, onRerun }: LessonScreenProps) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [rerunning, setRerunning] = useState(false)
  const [splitting, setSplitting] = useState(false)

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

  const canRerun = state.status === 'ready' && state.response.rerun_stages.length > 0

  // Cuts the lesson as it is laid out now; the saved lines then stay with their blocks.
  const split = async (days: number): Promise<string | null> => {
    const root = document.querySelector<HTMLElement>('.lesson')
    const end = root ? lessonEnd(root) : null
    const starts = root && end !== null ? splitDays(boundaries(root), end, days) : []
    try {
      await saveDays(lessonId, starts)
    } catch (err) {
      return err instanceof ApiError ? err.message : 'Could not reach the server.'
    }
    setState((current) =>
      current.status === 'ready' ? { ...current, response: { ...current.response, day_starts: starts } } : current
    )
    setSplitting(false)
    return null
  }

  return (
    <>
      <nav className="screen-nav lesson-nav">
        <button type="button" className="link-button" onClick={onBack}>
          Library
        </button>
        <div className="lesson-actions">
          {state.status === 'ready' && (
            <button type="button" className="button" onClick={() => setSplitting(true)}>
              Days
            </button>
          )}
          {canRerun && (
            <button type="button" className="button" onClick={() => setRerunning(true)}>
              Rerun
            </button>
          )}
        </div>
      </nav>
      {state.status === 'loading' && <p className="screen-message">Loading lesson</p>}
      {state.status === 'error' && <p className="screen-message">Could not load the lesson: {state.message}</p>}
      {state.status === 'unavailable' && <p className="screen-message">{state.message}</p>}
      {state.status === 'ready' && (
        <>
          {state.response.error && <p className="notice">{state.response.error}</p>}
          <ProgressProvider key={lessonId} lessonId={lessonId} initial={state.progress}>
            <LessonView
              lesson={state.lesson}
              readingBlock={state.response.reading_block}
              dayStarts={state.response.day_starts}
            />
          </ProgressProvider>
          {splitting && (
            <DaysDialog
              current={state.response.day_starts.length + 1}
              max={Math.min(MAX_DAYS, state.lesson.sections.reduce((count, s) => count + s.blocks.length, 0))}
              onSplit={split}
              onCancel={() => setSplitting(false)}
            />
          )}
          {rerunning && (
            <RerunDialog
              lessonId={lessonId}
              status={state.response}
              onCancel={() => setRerunning(false)}
              onStarted={() => onRerun(lessonId)}
            />
          )}
        </>
      )}
    </>
  )
}

async function load(lessonId: string): Promise<State> {
  const body = await getLesson(lessonId)
  if (body.status !== 'ready' || !body.lesson) {
    return { status: 'unavailable', message: UNAVAILABLE[body.status === 'failed' ? 'failed' : 'generating'] }
  }
  return { status: 'ready', lesson: body.lesson, progress: await getProgress(lessonId), response: body }
}

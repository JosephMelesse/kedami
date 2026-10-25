import { useEffect, useState } from 'react'
import { cancelLesson, getLesson, type LessonResponse } from '../api'
import { ConfirmDialog } from '../ConfirmDialog'
import { Game2048 } from '../game/Game2048'
import { RerunDialog } from './RerunDialog'
import { STAGES } from './stages'

const POLL_MS = 2000

interface GeneratingProps {
  lessonId: string
  onReady: (lessonId: string) => void
  onBack: () => void
}

export function GeneratingScreen({ lessonId, onReady, onBack }: GeneratingProps) {
  const [status, setStatus] = useState<LessonResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rerunning, setRerunning] = useState(false)
  const [canceling, setCanceling] = useState(false)
  // Bumped after a rerun starts, to resume polling.
  const [run, setRun] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const next = await getLesson(lessonId)
        if (cancelled) return
        if (next.status === 'ready') return onReady(lessonId)
        setStatus(next)
        if (next.status === 'generating') timer = setTimeout(poll, POLL_MS)
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    }
    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [lessonId, onReady, run])

  return (
    <>
      <nav className="screen-nav">
        <button type="button" className="link-button" onClick={onBack}>
          Library
        </button>
      </nav>
      <div className="form-screen">
        <GeneratingView
          status={status}
          error={error}
          onRerun={() => setRerunning(true)}
          onCancel={() => setCanceling(true)}
        />
      </div>
      {canceling && (
        <ConfirmDialog
          title="Cancel this lesson?"
          body="Claude Code's build stops here and the lesson is marked failed. You can delete it from the library."
          confirmLabel="Cancel lesson"
          destructive
          onCancel={() => setCanceling(false)}
          onConfirm={async () => {
            setCanceling(false)
            try {
              await cancelLesson(lessonId)
              setRun(run + 1)
            } catch (err) {
              setError((err as Error).message)
            }
          }}
        />
      )}
      {rerunning && status && (
        <RerunDialog
          lessonId={lessonId}
          status={status}
          onCancel={() => setRerunning(false)}
          onStarted={() => {
            setRerunning(false)
            setStatus(null)
            setRun(run + 1)
          }}
        />
      )}
    </>
  )
}

interface GeneratingViewProps {
  status: LessonResponse | null
  error: string | null
  onRerun?: () => void
  /** Ends a build Claude Code is doing. */
  onCancel?: () => void
}

export function GeneratingView({ status, error, onRerun, onCancel }: GeneratingViewProps) {
  if (error) return <p className="muted">Could not check on the lesson: {error}</p>
  if (!status) return <p className="muted">Checking on the lesson</p>

  const failed = status.status === 'failed'
  const current = status.current_stage ?? 0
  const agent = status.builder === 'agent'
  // An agent lesson has no stage until Claude Code starts it.
  const waiting = agent && !failed && status.current_stage === null
  return (
    <>
      <header className="lesson-header">
        <h1>{failed ? 'Generation failed' : waiting ? 'Waiting for Claude Code' : 'Generating your lesson'}</h1>
        {failed ? (
          <p className="muted">{status.error}</p>
        ) : waiting ? (
          <p className="muted">
            Open the Terminal, start Claude Code, and run <code>/kedami:lesson</code>. It builds the lesson from your
            files, and this page follows along.
          </p>
        ) : (
          <p className="muted">
            {agent
              ? 'Claude Code is building it. You can go back to the library; it keeps running.'
              : 'This takes a few minutes. You can go back to the library; it keeps running.'}
          </p>
        )}
      </header>
      <ol className="stages">
        {STAGES.map(({ stage, label }) => {
          const state = stage < current ? 'done' : stage === current ? (failed ? 'failed' : 'current') : 'pending'
          return (
            <li key={stage} className="stage" data-state={state}>
              <span className="stage-marker" aria-hidden="true" />
              {label}
            </li>
          )
        })}
      </ol>
      {!failed && <Game2048 />}
      {agent && !failed && onCancel && (
        <div>
          <button type="button" className="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      )}
      {failed && status.rerun_stages.length > 0 && onRerun && (
        <div>
          <button type="button" className="button button-primary" onClick={onRerun}>
            Rerun
          </button>
        </div>
      )}
    </>
  )
}

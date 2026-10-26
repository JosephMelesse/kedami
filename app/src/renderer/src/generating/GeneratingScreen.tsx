import { useEffect, useState } from 'react'
import { buildIsWaiting, cancelLesson, getJobs, getLesson, type LessonResponse } from '../api'
import { ConfirmDialog } from '../ConfirmDialog'
import { Game2048 } from '../game/Game2048'
import { STAGES } from './stages'

const POLL_MS = 2000

interface GeneratingProps {
  lessonId: string
  onReady: (lessonId: string) => void
  onBack: () => void
}

export function GeneratingScreen({ lessonId, onReady, onBack }: GeneratingProps) {
  const [status, setStatus] = useState<LessonResponse | null>(null)
  const [behind, setBehind] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [canceling, setCanceling] = useState(false)
  // Bumped after a cancel, to check on the lesson again.
  const [run, setRun] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const next = await getLesson(lessonId)
        if (cancelled) return
        if (next.status === 'ready') return onReady(lessonId)
        // Only asked before the first stage: after that the build is plainly running.
        const queue = next.status === 'generating' && next.current_stage === null ? await getJobs() : null
        if (cancelled) return
        setBehind(buildIsWaiting(queue, lessonId))
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
        <GeneratingView status={status} behind={behind} error={error} onCancel={() => setCanceling(true)} />
      </div>
      {canceling && (
        <ConfirmDialog
          title="Cancel this lesson?"
          body="Claude Code stops building it and the lesson is marked failed. You can delete it from the library."
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
    </>
  )
}

interface GeneratingViewProps {
  status: LessonResponse | null
  /** Whether the build is queued behind another Claude Code job. */
  behind?: boolean
  error: string | null
  /** Ends a build Claude Code is doing. */
  onCancel?: () => void
}

export function GeneratingView({ status, behind = false, error, onCancel }: GeneratingViewProps) {
  if (error) return <p className="muted">Could not check on the lesson: {error}</p>
  if (!status) return <p className="muted">Checking on the lesson</p>

  const failed = status.status === 'failed'
  const current = status.current_stage ?? 0
  // A lesson has no stage until Claude Code's build job reaches its first step.
  const starting = !failed && status.current_stage === null
  const title = failed
    ? 'Generation failed'
    : starting
      ? behind
        ? 'Waiting for another job'
        : 'Starting Claude Code'
      : 'Generating your lesson'
  return (
    <>
      <header className="lesson-header">
        <h1>{title}</h1>
        {failed ? (
          <p className="muted">{status.error}</p>
        ) : starting && behind ? (
          <p className="muted">Claude Code is busy with another job. This build starts as soon as it finishes.</p>
        ) : (
          <p className="muted">Claude Code is building it. You can go back to the library; it keeps running.</p>
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
      {!failed && onCancel && (
        <div>
          <button type="button" className="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      )}
    </>
  )
}

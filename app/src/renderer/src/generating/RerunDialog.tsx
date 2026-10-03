import { useEffect, useRef, useState } from 'react'
import { ApiError, type LessonResponse, rerunLesson } from '../api'
import { canForce } from './files'
import { STAGES } from './stages'

interface RerunDialogProps {
  lessonId: string
  status: LessonResponse
  onStarted: () => void
  onCancel: () => void
}

/** Mount it to open it, as a modal. */
export function RerunDialog({ lessonId, status, onStarted, onCancel }: RerunDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const [force, setForce] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(status.materials.map((m) => [m.id, m.force_transcription]))
  )
  const changed = status.materials.some((m) => force[m.id] !== m.force_transcription)
  const allowed = (stage: number) => status.rerun_stages.includes(stage) && (stage === 1 || !changed)
  const [stage, setStage] = useState(() => status.rerun_stages[0] ?? 1)
  const chosen = allowed(stage) ? stage : 1
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal()
  }, [])

  const start = async () => {
    setPending(true)
    setError(null)
    try {
      await rerunLesson(lessonId, chosen, force)
      onStarted()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.')
      setPending(false)
    }
  }

  return (
    <dialog
      ref={ref}
      className="dialog rerun-dialog"
      onCancel={(event) => {
        event.preventDefault()
        onCancel()
      }}
    >
      <h2>Rerun this lesson</h2>
      <p className="muted">
        Progress carries over: marked-done parts stay done and saved answers are rechecked. Checkpoint progress resets.
      </p>
      <fieldset className="field">
        <legend className="field-label">Start from</legend>
        {STAGES.map(({ stage: value, label }) => (
          <label key={value} className="option">
            <input
              type="radio"
              name="stage"
              checked={chosen === value}
              disabled={!allowed(value)}
              onChange={() => setStage(value)}
            />
            {value}. {label}
          </label>
        ))}
      </fieldset>
      <fieldset className="field">
        <legend className="field-label">Force transcription</legend>
        {status.materials.map((material) => (
          <label key={material.id} className="option">
            <input
              type="checkbox"
              checked={force[material.id]}
              disabled={!canForce(material.filename)}
              onChange={(event) => setForce({ ...force, [material.id]: event.target.checked })}
            />
            {material.filename}
          </label>
        ))}
        {changed && <p className="muted">Changing force transcription reruns from stage 1.</p>}
      </fieldset>
      {error && <p className="answer-error">{error}</p>}
      <div className="dialog-actions">
        <button type="button" className="button" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="button button-primary" disabled={pending} onClick={start}>
          Rerun
        </button>
      </div>
    </dialog>
  )
}

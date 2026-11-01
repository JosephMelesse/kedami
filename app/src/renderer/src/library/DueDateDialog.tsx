import { type FormEvent, useEffect, useRef, useState } from 'react'

interface DueDateDialogProps {
  title: string
  /** The due date it has, as YYYY-MM-DD. */
  initial: string | null
  /** Saves a date, or clears it with null. Resolves to an error message to show, or null when done. */
  onSubmit: (date: string | null) => Promise<string | null>
  onCancel: () => void
}

/** Sets, changes, or clears a lesson's due date. Mount it to open it. */
export function DueDateDialog({ title, initial, onSubmit, onCancel }: DueDateDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const [date, setDate] = useState(initial ?? '')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal()
  }, [])

  const send = async (value: string | null) => {
    if (pending) return
    setPending(true)
    const message = await onSubmit(value)
    setPending(false)
    setError(message)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (date) send(date)
  }

  return (
    <dialog
      ref={ref}
      className="dialog"
      onCancel={(event) => {
        event.preventDefault()
        onCancel()
      }}
    >
      <form className="dialog-form" onSubmit={submit}>
        <h2>{title}</h2>
        <input
          type="date"
          className="text-input"
          aria-label="Due date"
          value={date}
          onChange={(event) => setDate(event.target.value)}
          autoFocus
        />
        {error && <p className="answer-error">{error}</p>}
        <div className="dialog-actions">
          {initial !== null && (
            <button type="button" className="button" disabled={pending} onClick={() => send(null)}>
              Clear
            </button>
          )}
          <button type="button" className="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="button button-primary" disabled={!date || pending}>
            Save
          </button>
        </div>
      </form>
    </dialog>
  )
}

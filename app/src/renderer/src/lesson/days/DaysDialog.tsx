import { type FormEvent, useEffect, useRef, useState } from 'react'

interface DaysDialogProps {
  /** The number of days the lesson is split into now. */
  current: number
  max: number
  /** Resolves to an error message to show, or null when done. */
  onSplit: (days: number) => Promise<string | null>
  onCancel: () => void
}

/** Asks how many days to split the lesson into. Mount it to open it. */
export function DaysDialog({ current, max, onSplit, onCancel }: DaysDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const [text, setText] = useState(String(current))
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const days = /^\d+$/.test(text.trim()) ? Number(text.trim()) : NaN
  const valid = days >= 1 && days <= max

  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal()
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!valid || pending) return
    setPending(true)
    const message = await onSplit(days)
    setPending(false)
    setError(message)
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
        <h2>Split into days</h2>
        <p className="muted">
          Each day ends at a finish line, at the block nearest to an equal share of the lesson. 1 day removes the lines.
        </p>
        <label className="field">
          <span className="field-label">Days, 1 to {max}</span>
          <input
            className="text-input"
            inputMode="numeric"
            value={text}
            onChange={(event) => setText(event.target.value)}
            autoFocus
          />
        </label>
        {error && <p className="answer-error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="button button-primary" disabled={!valid || pending}>
            Split
          </button>
        </div>
      </form>
    </dialog>
  )
}

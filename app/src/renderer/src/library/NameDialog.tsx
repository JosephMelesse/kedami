import { type FormEvent, useEffect, useRef, useState } from 'react'

interface NameDialogProps {
  title: string
  confirmLabel: string
  /** Resolves to an error message to show, or null when done. */
  onSubmit: (name: string) => Promise<string | null>
  onCancel: () => void
}

/** Asks for a name. Mount it to open it. */
export function NameDialog({ title, confirmLabel, onSubmit, onCancel }: NameDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal()
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim() || pending) return
    setPending(true)
    const message = await onSubmit(name.trim())
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
        <h2>{title}</h2>
        <input
          className="text-input"
          aria-label="Name"
          maxLength={80}
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoFocus
        />
        {error && <p className="answer-error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="button button-primary" disabled={!name.trim() || pending}>
            {confirmLabel}
          </button>
        </div>
      </form>
    </dialog>
  )
}

import { useEffect, useRef, useState } from 'react'
import type { MoveTarget } from './folders'

interface MoveDialogProps {
  title: string
  targets: MoveTarget[]
  /** Resolves to an error message to show, or null when done. */
  onPick: (folderId: number | null) => Promise<string | null>
  onCancel: () => void
}

/** Asks where to move a lesson or folder. Mount it to open it. */
export function MoveDialog({ title, targets, onPick, onCancel }: MoveDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal()
  }, [])

  const pick = async (folderId: number | null) => {
    if (pending) return
    setPending(true)
    const message = await onPick(folderId)
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
      <h2>{title}</h2>
      <ul className="move-list">
        {targets.map((target) => (
          <li key={target.id ?? 'home'}>
            <button type="button" disabled={target.disabled || pending} onClick={() => pick(target.id)}>
              {target.label}
            </button>
          </li>
        ))}
      </ul>
      {error && <p className="answer-error">{error}</p>}
      <div className="dialog-actions">
        <button type="button" className="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </dialog>
  )
}

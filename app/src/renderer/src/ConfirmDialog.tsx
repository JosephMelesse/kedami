import { useEffect, useRef } from 'react'

// Mount it to open it, as a modal; unmount it to close it.
interface ConfirmDialogProps {
  title: string
  body: string
  confirmLabel: string
  /** Focus Cancel rather than the action, so Enter can't confirm something irreversible. */
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({ title, body, confirmLabel, destructive = false, onConfirm, onCancel }: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal()
  }, [])

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
      <p className="muted">{body}</p>
      <div className="dialog-actions">
        <button type="button" className="button" onClick={onCancel} autoFocus={destructive}>
          Cancel
        </button>
        <button type="button" className="button button-primary" onClick={onConfirm} autoFocus={!destructive}>
          {confirmLabel}
        </button>
      </div>
    </dialog>
  )
}

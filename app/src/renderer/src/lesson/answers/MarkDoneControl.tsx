import { useState } from 'react'
import { ConfirmDialog } from '../../ConfirmDialog'
import type { PartState } from '../progress/state'

interface MarkDoneControlProps {
  name: string
  state: PartState
  onChange: (done: boolean) => void
}

export function MarkDoneControl({ name, state, onChange }: MarkDoneControlProps) {
  const [confirming, setConfirming] = useState(false)

  if (state === 'correct') return null
  if (state === 'marked_done') {
    return (
      <button type="button" className="link-button" onClick={() => onChange(false)}>
        Undo mark done
      </button>
    )
  }
  return (
    <>
      <button type="button" className="button" onClick={() => setConfirming(true)}>
        Mark done
      </button>
      {confirming && (
        <ConfirmDialog
          title={`Mark ${name} as done?`}
          body="Your answer won't be checked. You can undo this later."
          confirmLabel="Mark done"
          onCancel={() => setConfirming(false)}
          onConfirm={() => {
            setConfirming(false)
            onChange(true)
          }}
        />
      )}
    </>
  )
}

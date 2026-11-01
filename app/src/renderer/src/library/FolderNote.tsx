import { useState } from 'react'
import { saveFolderNote } from '../api'
import { useAutosave } from '../code/useAutosave'

const MAX_NOTE = 20_000

interface FolderNoteProps {
  folderId: number
  /** The saved note. Read once: give each folder its own key, so a background refresh never replaces what is typed. */
  initial: string
  /** Told of every change, so a delete confirmation and a return to this folder see the latest text. */
  onChange: (note: string) => void
}

/** A folder's own note, saved as it is typed. See Folder notes in architecture/ui.md. */
export function FolderNote({ folderId, initial, onChange }: FolderNoteProps) {
  const [text, setText] = useState(initial)
  const [failed, setFailed] = useState(false)

  useAutosave(text, async (value) => {
    try {
      await saveFolderNote(folderId, value)
      setFailed(false)
    } catch {
      setFailed(true)
    }
  })

  return (
    <div className="folder-note">
      <textarea
        className="text-input"
        aria-label="Folder note"
        placeholder="Notes for this folder"
        rows={3}
        maxLength={MAX_NOTE}
        value={text}
        onChange={(event) => {
          setText(event.target.value)
          onChange(event.target.value)
        }}
      />
      {failed && <p className="answer-error">Could not save this note. Keep typing to try again.</p>}
    </div>
  )
}

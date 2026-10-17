// Saving typed text when typing stops for a second, and on leaving with unsaved changes.
// Shared by the code and SQL workspaces; see architecture/code-problems.md, Workspace.

import { useEffect, useRef } from 'react'

/** How long typing must stop before the text is saved. */
export const SAVE_DELAY_MS = 1000

export interface Autosave {
  /** Save now if the text changed since the last save, such as before a Run. */
  saveNow(text: string): Promise<void>
  /** Note text that was saved another way, such as with a Submit. */
  markSaved(text: string): void
}

export function useAutosave(text: string, save: (text: string) => Promise<void>): Autosave {
  const saved = useRef(text)
  const latest = useRef({ text, save })
  latest.current = { text, save }

  const saveNow = async (value: string): Promise<void> => {
    if (value === saved.current) return
    saved.current = value
    await latest.current.save(value)
  }

  useEffect(() => {
    if (text === saved.current) return
    const timer = setTimeout(() => saveNow(text), SAVE_DELAY_MS)
    return () => clearTimeout(timer)
  })
  useEffect(
    () => () => {
      const { text: last, save: lastSave } = latest.current
      if (last !== saved.current) lastSave(last)
    },
    []
  )

  return { saveNow, markSaved: (value) => (saved.current = value) }
}

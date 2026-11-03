// Saving typed text when typing stops for a second, and on leaving with unsaved changes.

import { useEffect, useRef } from 'react'

/** How long typing must stop before the text is saved. */
const SAVE_DELAY_MS = 1000

export function useAutosave(text: string, save: (text: string) => Promise<void>): void {
  const saved = useRef(text)
  const latest = useRef({ text, save })
  latest.current = { text, save }

  useEffect(() => {
    if (text === saved.current) return
    const timer = setTimeout(() => {
      saved.current = text
      latest.current.save(text)
    }, SAVE_DELAY_MS)
    return () => clearTimeout(timer)
  })
  useEffect(
    () => () => {
      const { text: last, save: lastSave } = latest.current
      if (last !== saved.current) lastSave(last)
    },
    []
  )
}

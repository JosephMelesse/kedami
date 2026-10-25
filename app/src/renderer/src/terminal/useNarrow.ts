import { useEffect, useState } from 'react'

const NARROW = '(max-width: 720px)'

/** Whether the window is 720px wide or less, the narrow layout in architecture/ui.md. */
export function useNarrow(): boolean {
  const query = () => (typeof window.matchMedia === 'function' ? window.matchMedia(NARROW) : null)
  const [narrow, setNarrow] = useState(() => query()?.matches ?? false)
  useEffect(() => {
    const list = query()
    if (!list) return
    const update = () => setNarrow(list.matches)
    list.addEventListener('change', update)
    return () => list.removeEventListener('change', update)
  }, [])
  return narrow
}

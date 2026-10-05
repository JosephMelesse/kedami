import { type RefObject, useEffect } from 'react'
import { useSetDayBar } from './DayBar'
import { measureDays, NOTE_MS } from './days'

/**
 * Keeps the header's bar at the day progress while the lesson is open, and shows "Done for today"
 * when scrolling passes a finish line. Measuring starts once the lesson has jumped to its reading
 * position, so opening a lesson past a line shows no note.
 */
export function useFinishLines(root: RefObject<HTMLElement | null>, dayStarts: readonly string[], opened: boolean) {
  const setBar = useSetDayBar()

  useEffect(() => {
    if (!opened) return
    let reached: number | null = null
    let fill = 0
    let note = false
    let shown: string | null = null
    let timer: ReturnType<typeof setTimeout> | undefined

    const publish = () => {
      const bar = { fill: note ? 1 : fill, note }
      const key = `${bar.fill.toFixed(3)} ${bar.note}`
      if (key === shown) return
      shown = key
      setBar(bar)
    }

    const measure = () => {
      const progress = root.current ? measureDays(root.current) : null
      if (!progress) return
      if (reached !== null && progress.reached > reached) {
        note = true
        clearTimeout(timer)
        timer = setTimeout(() => {
          note = false
          publish()
        }, NOTE_MS)
      }
      reached = progress.reached
      fill = progress.fill
      publish()
    }

    measure()
    window.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    return () => {
      window.removeEventListener('scroll', measure)
      window.removeEventListener('resize', measure)
      clearTimeout(timer)
      setBar(null)
    }
  }, [root, dayStarts, opened, setBar])
}

import { type RefObject, useEffect, useState } from 'react'
import { saveReadingPosition } from '../../api'
import { blockElements, headerBottom, readingBlock, SAVE_DELAY_MS } from './readingPosition'

/**
 * Opens the lesson at the saved block, then saves the block being read once scrolling stops
 * and when the lesson closes. Chromium's scroll anchoring keeps the block in place if content
 * above it changes height after the jump. Returns whether the jump is done.
 */
export function useReadingPosition(lessonId: string, saved: string | null, root: RefObject<HTMLElement | null>) {
  const [opened, setOpened] = useState(false)

  useEffect(() => {
    let cancelled = false
    let lastSaved = saved
    let current: string | null = null
    let timer: ReturnType<typeof setTimeout> | undefined

    const save = (blockId: string) => {
      if (blockId === lastSaved) return
      saveReadingPosition(lessonId, blockId)
        .then(() => (lastSaved = blockId))
        // Losing a reading position is harmless; the next save tries again.
        .catch(() => {})
    }

    // Wait for the bundled fonts so the jump measures the final layout.
    void (document.fonts?.ready ?? Promise.resolve()).then(() => {
      if (cancelled || !root.current) return
      const target = saved ? root.current.querySelector<HTMLElement>(`[data-block-id="${CSS.escape(saved)}"]`) : null
      const top = target ? target.getBoundingClientRect().top + window.scrollY - headerBottom() : 0
      window.scrollTo({ top, behavior: 'instant' })
      setOpened(true)
    })

    const onScroll = () => {
      if (!root.current) return
      current = readingBlock(blockElements(root.current), headerBottom())?.dataset.blockId ?? null
      clearTimeout(timer)
      timer = setTimeout(() => current && save(current), SAVE_DELAY_MS)
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      cancelled = true
      window.removeEventListener('scroll', onScroll)
      clearTimeout(timer)
      if (current) save(current)
    }
  }, [lessonId, saved, root])

  return opened
}

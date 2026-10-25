import { type PointerEvent as ReactPointerEvent, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { clampWidth } from './panelWidth'

interface TerminalPanelProps {
  width: number
  /** In a narrow window the panel covers the screen below the header, at no particular width. */
  narrow: boolean
  onWidth: (width: number) => void
}

/**
 * The Terminal panel on the right. The terminal itself is a separate view that main lays over the slot, so this
 * window never touches it; see architecture/agent-mode.md, Isolation. Unmounting hides the view, and its session
 * keeps running.
 */
export function TerminalPanel({ width, narrow, onWidth }: TerminalPanelProps) {
  const slot = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState(false)

  // The view would take the pointer while dragging over it, so it hides until the drag ends.
  useLayoutEffect(() => {
    if (dragging) {
      window.kedami.hideTerminal()
      return
    }
    const element = slot.current!
    const show = () => {
      const rect = element.getBoundingClientRect()
      window.kedami.showTerminal({
        x: Math.round(rect.left),
        y: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      })
    }
    show()
    window.addEventListener('resize', show)
    return () => window.removeEventListener('resize', show)
  }, [width, narrow, dragging])

  useEffect(() => () => window.kedami.hideTerminal(), [])

  const drag = (event: ReactPointerEvent) => {
    event.preventDefault()
    setDragging(true)
    const move = (moved: PointerEvent) => onWidth(clampWidth(window.innerWidth - moved.clientX, window.innerWidth))
    const end = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', end)
      setDragging(false)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', end)
  }

  return (
    <aside className="terminal-panel" data-narrow={narrow} style={narrow ? undefined : { width }}>
      {!narrow && (
        <div
          className="terminal-handle"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize the terminal"
          data-dragging={dragging}
          onPointerDown={drag}
        />
      )}
      <div ref={slot} className="terminal-slot" />
    </aside>
  )
}

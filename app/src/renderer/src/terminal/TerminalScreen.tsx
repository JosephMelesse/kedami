import { useLayoutEffect, useRef } from 'react'

/**
 * The space below the header that the Terminal screen fills. The terminal itself is a separate view that
 * main lays over this space, so this window never touches it; see architecture/agent-mode.md, Isolation.
 * Unmounting hides the view, and its session keeps running.
 */
export function TerminalScreen() {
  const area = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const element = area.current!
    // The area is fixed below the header, so only the window's size changes it.
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
    return () => {
      window.removeEventListener('resize', show)
      window.kedami.hideTerminal()
    }
  }, [])

  return <div ref={area} className="terminal-area" />
}

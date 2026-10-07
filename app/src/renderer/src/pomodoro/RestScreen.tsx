import { useEffect } from 'react'
import { Game2048 } from '../game/Game2048'

/**
 * Covers everything below the app header during rest, with a 2048 game below the countdown.
 * The screen underneath stays mounted, and the page can't scroll, so it comes back where it was.
 */
export function RestScreen({ time }: { time: string }) {
  useEffect(() => {
    document.documentElement.classList.add('resting')
    return () => document.documentElement.classList.remove('resting')
  }, [])

  return (
    <section className="rest-screen fade-in" aria-label="Rest">
      <h1 className="rest-code">404</h1>
      <p className="rest-caption">
        You can go back to studying in <span className="rest-time">{time}</span>
      </p>
      <Game2048 />
    </section>
  )
}

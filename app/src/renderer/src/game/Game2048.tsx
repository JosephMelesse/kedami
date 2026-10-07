import { useEffect, useRef, useSyncExternalStore, type CSSProperties } from 'react'
import type { Direction } from './board'
import { getGame, move, restart, subscribe } from './store'

const KEYS: Record<string, Direction> = {
  ArrowLeft: 'left',
  ArrowRight: 'right',
  ArrowUp: 'up',
  ArrowDown: 'down'
}

export function Game2048() {
  const game = useSyncExternalStore(subscribe, getGame, getGame)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const direction = KEYS[event.key]
      if (!direction || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
      // Under the rest screen, or while typing a duration or picking a track, keys are not moves.
      if (ref.current?.closest('[inert]')) return
      if (event.target instanceof Element && event.target.closest('input, select, textarea')) return
      event.preventDefault()
      move(direction)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="game" ref={ref} role="group" aria-label="2048">
      <div className="game-board">
        {game.board.map((value, cell) => (
          <div key={cell} className="game-cell">
            {value > 0 && (
              <span
                key={cell === game.added ? `added-${game.turn}` : 'tile'}
                className={cell === game.added ? 'game-tile fade-in' : 'game-tile'}
                data-digits={Math.min(String(value).length, 5)}
                data-strong={value >= 256}
                style={{ '--level': Math.min(Math.log2(value), 11) } as CSSProperties}
              >
                {value}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="game-footer">
        <span className="game-score">
          Score <span className="game-score-value">{game.score}</span>
        </span>
        {game.over && <span className="game-over">No moves left</span>}
        <button type="button" className="button" onClick={restart}>
          New game
        </button>
      </div>
    </div>
  )
}

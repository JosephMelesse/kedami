import { newGame, play, type Direction, type Game } from './board'

// One game for the app session, shared by the Generating and rest screens.
let game = newGame(Math.random)
const listeners = new Set<() => void>()

function set(next: Game) {
  if (next === game) return
  game = next
  listeners.forEach((listener) => listener())
}

export function getGame(): Game {
  return game
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function move(direction: Direction) {
  set(play(game, direction, Math.random))
}

export function restart() {
  set(newGame(Math.random))
}

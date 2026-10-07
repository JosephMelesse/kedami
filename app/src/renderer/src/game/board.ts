/** 2048 rules. The board is 16 cells in row order, with 0 for an empty cell. */

export type Board = number[]
export type Direction = 'left' | 'right' | 'up' | 'down'
export type Random = () => number

export interface Game {
  board: Board
  score: number
  // The cell of the tile added by the last move, so it can fade in.
  added: number | null
  // Counts moves, so a tile added to the same cell twice still fades in.
  turn: number
  over: boolean
}

const SIZE = 4

// The cells of each line, listed in the order tiles slide toward.
const LINES: Record<Direction, number[][]> = {
  left: range().map((r) => range().map((c) => r * SIZE + c)),
  right: range().map((r) => range().map((c) => r * SIZE + SIZE - 1 - c)),
  up: range().map((c) => range().map((r) => r * SIZE + c)),
  down: range().map((c) => range().map((r) => (SIZE - 1 - r) * SIZE + c))
}

function range(): number[] {
  return [...Array(SIZE).keys()]
}

/** Slides one line toward its start. Each tile merges at most once. */
export function slideLine(line: number[]): { line: number[]; gained: number } {
  const tiles = line.filter((v) => v > 0)
  const out: number[] = []
  let gained = 0
  for (let i = 0; i < tiles.length; i++) {
    if (tiles[i] === tiles[i + 1]) {
      out.push(tiles[i] * 2)
      gained += tiles[i] * 2
      i++
    } else {
      out.push(tiles[i])
    }
  }
  while (out.length < line.length) out.push(0)
  return { line: out, gained }
}

export function slide(board: Board, direction: Direction): { board: Board; gained: number; moved: boolean } {
  const next = [...board]
  let gained = 0
  for (const cells of LINES[direction]) {
    const result = slideLine(cells.map((i) => board[i]))
    cells.forEach((cell, k) => (next[cell] = result.line[k]))
    gained += result.gained
  }
  return { board: next, gained, moved: next.some((v, i) => v !== board[i]) }
}

/** Puts a 2, or a 4 one time in ten, in a random empty cell. Returns null for a full board. */
export function addTile(board: Board, random: Random): { board: Board; cell: number } | null {
  const empty = board.flatMap((v, i) => (v === 0 ? [i] : []))
  if (empty.length === 0) return null
  const cell = empty[Math.floor(random() * empty.length)]
  const next = [...board]
  next[cell] = random() < 0.9 ? 2 : 4
  return { board: next, cell }
}

export function canMove(board: Board): boolean {
  return board.some((v, i) => {
    if (v === 0) return true
    const right = i % SIZE < SIZE - 1 && board[i + 1] === v
    const below = i + SIZE < board.length && board[i + SIZE] === v
    return right || below
  })
}

export function newGame(random: Random): Game {
  const first = addTile(Array(SIZE * SIZE).fill(0), random)!
  const second = addTile(first.board, random)!
  return { board: second.board, score: 0, added: null, turn: 0, over: false }
}

/** Plays one move. A move that changes nothing, or a finished game, returns the same game. */
export function play(game: Game, direction: Direction, random: Random): Game {
  if (game.over) return game
  const { board, gained, moved } = slide(game.board, direction)
  if (!moved) return game
  // A move that changed the board left at least one cell empty.
  const added = addTile(board, random)!
  return {
    board: added.board,
    score: game.score + gained,
    added: added.cell,
    turn: game.turn + 1,
    over: !canMove(added.board)
  }
}

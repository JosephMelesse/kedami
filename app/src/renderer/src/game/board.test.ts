import { describe, expect, it } from 'vitest'
import { addTile, canMove, newGame, play, slide, slideLine, type Game } from './board'

// Always picks the first empty cell and a 2.
const first = () => 0

function game(board: number[], score = 0): Game {
  return { board, score, added: null, turn: 0, over: false }
}

describe('slideLine', () => {
  it('merges each tile at most once per move', () => {
    expect(slideLine([2, 2, 2, 2])).toEqual({ line: [4, 4, 0, 0], gained: 8 })
    expect(slideLine([2, 2, 4, 0])).toEqual({ line: [4, 4, 0, 0], gained: 4 })
    expect(slideLine([4, 4, 8, 0])).toEqual({ line: [8, 8, 0, 0], gained: 8 })
  })

  it('merges the pair nearest the edge first', () => {
    expect(slideLine([2, 2, 2, 0])).toEqual({ line: [4, 2, 0, 0], gained: 4 })
  })

  it('merges equal tiles across gaps, but not past a different tile', () => {
    expect(slideLine([4, 0, 0, 4])).toEqual({ line: [8, 0, 0, 0], gained: 8 })
    expect(slideLine([2, 4, 2, 0])).toEqual({ line: [2, 4, 2, 0], gained: 0 })
  })

  it('leaves an empty line empty', () => {
    expect(slideLine([0, 0, 0, 0])).toEqual({ line: [0, 0, 0, 0], gained: 0 })
  })
})

describe('slide', () => {
  const board = [
    2, 0, 2, 0,
    0, 0, 0, 0,
    0, 4, 0, 0,
    0, 4, 0, 8
  ]

  it('slides every line in each direction', () => {
    expect(slide(board, 'left').board).toEqual([4, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 4, 8, 0, 0])
    expect(slide(board, 'right').board).toEqual([0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 4, 8])
    expect(slide(board, 'up').board).toEqual([2, 8, 2, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    expect(slide(board, 'down').board).toEqual([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 8, 2, 8])
  })

  it('reports a move that changes nothing', () => {
    const packed = [2, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    expect(slide(packed, 'left').moved).toBe(false)
    expect(slide(packed, 'up').moved).toBe(false)
    expect(slide(packed, 'right').moved).toBe(true)
  })
})

describe('addTile', () => {
  it('puts a 2 or a 4 in an empty cell chosen at random', () => {
    const board = [2, 0, 2, 0, ...Array(12).fill(2)]
    expect(addTile(board, () => 0)).toEqual({ board: [2, 2, 2, 0, ...Array(12).fill(2)], cell: 1 })
    expect(addTile(board, () => 0.95)).toEqual({ board: [2, 0, 2, 4, ...Array(12).fill(2)], cell: 3 })
  })

  it('returns null for a full board', () => {
    expect(addTile(Array(16).fill(2), first)).toBeNull()
  })
})

describe('canMove', () => {
  it('is false only for a full board with no equal neighbours', () => {
    const stuck = [2, 4, 2, 4, 4, 2, 4, 2, 2, 4, 2, 4, 4, 2, 4, 2]
    expect(canMove(stuck)).toBe(false)
    expect(canMove(stuck.map((v, i) => (i === 5 ? 0 : v)))).toBe(true)
    expect(canMove(stuck.map((v, i) => (i === 1 ? 2 : v)))).toBe(true)
    expect(canMove(stuck.map((v, i) => (i === 4 ? 2 : v)))).toBe(true)
  })

  it('does not treat the end of one row and the start of the next as neighbours', () => {
    const wrap = [2, 4, 2, 8, 8, 2, 4, 2, 2, 4, 2, 4, 4, 2, 4, 2]
    expect(canMove(wrap)).toBe(false)
  })
})

describe('play', () => {
  it('starts with two tiles and no score', () => {
    const start = newGame(first)
    expect(start.board.filter((v) => v > 0)).toEqual([2, 2])
    expect([start.score, start.over]).toEqual([0, false])
  })

  it('adds the merged values to the score and adds one tile', () => {
    const next = play(game([2, 2, 4, 4, ...Array(12).fill(0)], 10), 'left', first)
    expect(next.board.slice(0, 4)).toEqual([4, 8, 2, 0])
    expect(next.score).toBe(22)
    expect([next.added, next.turn]).toEqual([2, 1])
  })

  it('returns the same game for a move that changes nothing', () => {
    const start = game([2, 4, ...Array(14).fill(0)])
    expect(play(start, 'left', first)).toBe(start)
  })

  it('ends the game when the added tile leaves no move', () => {
    const board = [2, 4, 2, 4, 4, 2, 4, 2, 2, 4, 2, 4, 0, 4, 2, 8]
    const next = play(game(board), 'left', first)
    expect(next.board).toEqual([2, 4, 2, 4, 4, 2, 4, 2, 2, 4, 2, 4, 4, 2, 8, 2])
    expect(next.over).toBe(true)
    expect(play(next, 'left', first)).toBe(next)
  })
})

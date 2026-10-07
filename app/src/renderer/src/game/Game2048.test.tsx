import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as board from './board'
import { Game2048 } from './Game2048'
import { restart } from './store'

vi.mock('./board', async (original) => {
  const actual = await original<typeof board>()
  return { ...actual, newGame: vi.fn(actual.newGame) }
})

const mounted: { root: Root; container: HTMLElement }[] = []

async function mount(parent: HTMLElement = document.body): Promise<HTMLElement> {
  const container = document.createElement('div')
  parent.append(container)
  const root = createRoot(container)
  await act(async () => root.render(<Game2048 />))
  mounted.push({ root, container })
  return container
}

const tiles = (container: HTMLElement) =>
  [...container.querySelectorAll('.game-cell')].map((cell) => Number(cell.textContent || 0))
const score = (container: HTMLElement) => container.querySelector('.game-score-value')?.textContent

async function press(key: string, target: EventTarget = window) {
  await act(async () => target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })))
}

describe('Game2048', () => {
  beforeEach(() => {
    // Every new tile is a 2 in the first empty cell, so a new game starts as two 2s in the top left.
    vi.spyOn(Math, 'random').mockReturnValue(0)
    restart()
  })

  afterEach(() => {
    for (const { root, container } of mounted.splice(0)) {
      act(() => root.unmount())
      container.remove()
    }
    document.body.innerHTML = ''
    vi.mocked(Math.random).mockRestore()
  })

  it('moves on arrow keys and shows the score below the board', async () => {
    const game = await mount()
    expect(tiles(game).slice(0, 4)).toEqual([2, 2, 0, 0])
    expect(score(game)).toBe('0')
    const footer = game.querySelector('.game-footer')!
    expect(game.querySelector('.game-board')!.compareDocumentPosition(footer)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)

    await press('ArrowRight')
    expect(tiles(game).slice(0, 4)).toEqual([2, 0, 0, 4])
    expect(score(game)).toBe('4')
    expect(game.querySelector('.fade-in')?.textContent).toBe('2')
  })

  it('stops an arrow key scrolling the page, and leaves other keys alone', async () => {
    await mount()
    const arrow = new KeyboardEvent('keydown', { key: 'ArrowDown', cancelable: true })
    const other = new KeyboardEvent('keydown', { key: 'PageDown', cancelable: true })
    await act(async () => {
      window.dispatchEvent(arrow)
      window.dispatchEvent(other)
    })
    expect([arrow.defaultPrevented, other.defaultPrevented]).toEqual([true, false])
  })

  it('ignores keys while typing in a field or picking from a dropdown', async () => {
    const game = await mount()
    for (const tag of ['input', 'select'] as const) {
      const field = document.body.appendChild(document.createElement(tag))
      await press('ArrowRight', field)
    }
    expect(tiles(game).slice(0, 4)).toEqual([2, 2, 0, 0])
  })

  it('moves the game on the rest screen only, not the one under it', async () => {
    const main = document.body.appendChild(document.createElement('main'))
    main.setAttribute('inert', '')
    const under = await mount(main)
    const rest = await mount()

    await press('ArrowRight')
    // Both show the one shared game, moved once.
    expect(tiles(rest).slice(0, 4)).toEqual([2, 0, 0, 4])
    expect(tiles(under)).toEqual(tiles(rest))
  })

  it('says when no move is left, and New game starts over', async () => {
    // One move left: sliding the bottom row left, after which the new tile locks the board.
    const nearlyLocked = [2, 4, 2, 4, 4, 2, 4, 2, 2, 4, 2, 4, 0, 4, 2, 8]
    vi.mocked(board.newGame).mockReturnValueOnce({ board: nearlyLocked, score: 12, added: null, turn: 0, over: false })
    restart()
    const game = await mount()
    expect(game.querySelector('.game-over')).toBeNull()
    await press('ArrowLeft')
    expect(game.querySelector('.game-over')?.textContent).toBe('No moves left')

    await act(async () => game.querySelector<HTMLButtonElement>('.game-footer button')!.click())
    expect(game.querySelector('.game-over')).toBeNull()
    expect(score(game)).toBe('0')
    expect(tiles(game).slice(0, 4)).toEqual([2, 2, 0, 0])
  })
})

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KedamiApi } from '../../preload/api'
import type { Folder, LessonSummary } from './api'
import { App } from './App'

const lesson: LessonSummary = {
  id: 'sample',
  title: 'Projectile motion',
  builder: 'pipeline',
  subject: 'physics',
  domain: null,
  status: 'ready',
  current_stage: null,
  error: null,
  folder_id: 3,
  created: '2026-10-03T00:00:00+00:00',
  problems_total: 2,
  problems_done: 0,
  active: false
}
const folder: Folder = { id: 3, name: 'Week 3', lessons: 1 }

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  listLessons: async () => [lesson],
  listFolders: async () => [folder]
}))

let container: HTMLDivElement
let root: Root
const shown: unknown[] = []
let hidden = 0
let toggles: (() => void)[] = []
let narrow = false

beforeEach(() => {
  shown.length = 0
  hidden = 0
  toggles = []
  narrow = false
  localStorage.clear()
  window.matchMedia = ((query: string) => ({
    matches: narrow && query === '(max-width: 720px)',
    addEventListener: () => {},
    removeEventListener: () => {}
  })) as unknown as typeof window.matchMedia
  window.kedami = {
    musicTracks: async () => [],
    showTerminal: (bounds: unknown) => void shown.push(bounds),
    hideTerminal: () => void hidden++,
    onTerminalToggle: (listener: () => void) => {
      toggles.push(listener)
      return () => (toggles = toggles.filter((t) => t !== listener))
    }
  } as unknown as KedamiApi
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

const heading = () => container.querySelector('h1')?.textContent
const click = (selector: string) => act(async () => container.querySelector<HTMLElement>(selector)!.click())

describe('App header', () => {
  it('goes to the home page from inside a folder when Kedami is clicked', async () => {
    await act(async () => root.render(<App />))
    expect(heading()).toBe('Lessons')
    await click('.tile')
    expect(heading()).toBe('Week 3')
    await click('.app-name')
    expect(heading()).toBe('Lessons')
  })
})

describe('Terminal panel', () => {
  const terminalButton = () => container.querySelector<HTMLButtonElement>('button[aria-label="Claude Code"]')!
  const panel = () => container.querySelector<HTMLElement>('.terminal-panel')
  const main = () => container.querySelector('main')!
  const width = () => document.documentElement.style.getPropertyValue('--terminal-width')

  it('opens beside the current screen, which stays usable, and closes again', async () => {
    await act(async () => root.render(<App />))
    await click('.tile')
    await act(async () => terminalButton().click())
    expect(panel()).not.toBeNull()
    expect(panel()!.dataset.narrow).toBe('false')
    expect(shown).toHaveLength(1)
    expect(main().hasAttribute('inert')).toBe(false)
    expect(width()).toBe(`${panel()!.style.width.replace('px', '')}px`)
    expect(terminalButton().getAttribute('aria-pressed')).toBe('true')

    await act(async () => terminalButton().click())
    expect(panel()).toBeNull()
    expect(hidden).toBe(1)
    expect(width()).toBe('0px')
    expect(heading()).toBe('Week 3')
  })

  it('stays open when Kedami is clicked', async () => {
    await act(async () => root.render(<App />))
    await click('.tile')
    await act(async () => terminalButton().click())
    await click('.app-name')
    expect(panel()).not.toBeNull()
    expect(heading()).toBe('Lessons')
  })

  it('opens and closes with the shortcut main reports', async () => {
    await act(async () => root.render(<App />))
    await act(async () => toggles.forEach((toggle) => toggle()))
    expect(panel()).not.toBeNull()
    await act(async () => toggles.forEach((toggle) => toggle()))
    expect(panel()).toBeNull()
  })

  it('covers the screen in a narrow window, which then takes no input', async () => {
    narrow = true
    await act(async () => root.render(<App />))
    await act(async () => terminalButton().click())
    expect(panel()!.dataset.narrow).toBe('true')
    expect(main().hasAttribute('inert')).toBe(true)
    expect(width()).toBe('0px')
  })

  it('resizes from its edge, hiding the view while dragging and keeping a usable width', async () => {
    Object.defineProperty(window, 'innerWidth', { value: 1200, configurable: true })
    await act(async () => root.render(<App />))
    await act(async () => terminalButton().click())
    const handle = container.querySelector<HTMLElement>('.terminal-handle')!
    await act(async () => handle.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true })))
    expect(hidden).toBe(1)
    await act(async () => window.dispatchEvent(new MouseEvent('pointermove', { clientX: 700 })))
    expect(panel()!.style.width).toBe('500px')
    await act(async () => window.dispatchEvent(new MouseEvent('pointermove', { clientX: 1100 })))
    expect(panel()!.style.width).toBe('320px')
    await act(async () => window.dispatchEvent(new MouseEvent('pointerup', {})))
    expect(shown.length).toBeGreaterThan(1)
    expect(localStorage.getItem('kedami.terminalWidth')).toBe('320')
  })
})

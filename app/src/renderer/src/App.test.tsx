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

beforeEach(() => {
  shown.length = 0
  hidden = 0
  window.kedami = {
    musicTracks: async () => [],
    showTerminal: (bounds: unknown) => void shown.push(bounds),
    hideTerminal: () => void hidden++
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

describe('Terminal screen', () => {
  const terminalButton = () => [...container.querySelectorAll('button')].find((b) => b.textContent === 'Terminal')!

  it('opens over the current screen, which keeps its state, and closes again', async () => {
    await act(async () => root.render(<App />))
    await click('.tile')
    await act(async () => terminalButton().click())
    expect(container.querySelector('.terminal-area')).not.toBeNull()
    expect(shown).toEqual([{ x: 0, y: 0, width: 0, height: 0 }])
    expect(container.querySelector('main')!.hasAttribute('inert')).toBe(true)
    expect(terminalButton().getAttribute('aria-pressed')).toBe('true')

    await act(async () => terminalButton().click())
    expect(container.querySelector('.terminal-area')).toBeNull()
    expect(hidden).toBe(1)
    expect(container.querySelector('main')!.hasAttribute('inert')).toBe(false)
    expect(heading()).toBe('Week 3')
  })

  it('closes when Kedami is clicked, which goes home', async () => {
    await act(async () => root.render(<App />))
    await click('.tile')
    await act(async () => terminalButton().click())
    await click('.app-name')
    expect(container.querySelector('.terminal-area')).toBeNull()
    expect(hidden).toBe(1)
    expect(heading()).toBe('Lessons')
  })
})

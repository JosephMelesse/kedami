import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KedamiApi } from '../../preload/api'
import type { Folder, LessonSummary } from './api'
import { App } from './App'

const lesson: LessonSummary = {
  id: 'sample',
  title: 'Projectile motion',
  subject: 'physics',
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

beforeEach(() => {
  window.kedami = { musicTracks: async () => [] } as unknown as KedamiApi
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

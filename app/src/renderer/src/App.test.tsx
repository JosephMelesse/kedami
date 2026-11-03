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
  active: false,
  due_date: null,
  done: false,
  overdue: false
}
const placeholder: LessonSummary = {
  ...lesson,
  id: 'planned',
  title: 'Exam review',
  subject: null,
  status: 'placeholder',
  problems_total: 0,
  problems_done: 0
}
const folder: Folder = { id: 3, name: 'Week 3', parent_id: null, lessons: 1, own_lessons: 1, subfolders: 0, note: '', next_due: null, next_due_overdue: false }

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  listLessons: async () => [lesson, placeholder],
  listFolders: async () => [folder],
  deleteFolder: async () => ({ parent_id: null, renamed: [{ id: 9, old: 'Week 1', new: 'Week 1 (2)' }] })
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

describe('Opening a placeholder', () => {
  it('goes to Upload under its name, and Back returns to its folder', async () => {
    await act(async () => root.render(<App />))
    await click('.tile')
    expect(heading()).toBe('Week 3')
    const tile = [...container.querySelectorAll<HTMLElement>('.tile')].find((t) => t.textContent?.includes('Exam review'))!
    await act(async () => tile.click())
    expect(heading()).toBe('Exam review')
    expect(container.querySelector('.form-screen')).not.toBeNull()
    await click('.screen-nav .link-button')
    expect(heading()).toBe('Week 3')
  })
})

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

describe('Deleting a folder', () => {
  it('lands on its parent with a notice of what was renamed, which stays on that page', async () => {
    HTMLDialogElement.prototype.showModal = function () {
      this.open = true
    }
    const button = (label: string) => [...container.querySelectorAll('button')].filter((b) => b.textContent === label).at(-1)!
    await act(async () => root.render(<App />))
    await click('.tile')
    await act(async () => button('Delete folder').click())
    await act(async () => button('Delete folder').click())
    expect(heading()).toBe('Lessons')
    expect(container.querySelector('.library-notice')?.textContent).toBe('Week 1 is now Week 1 (2), since that name was taken.')
    await click('.tile')
    expect(heading()).toBe('Week 3')
    expect(container.querySelector('.library-notice')).toBeNull()
  })
})

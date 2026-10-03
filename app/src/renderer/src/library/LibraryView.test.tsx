import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { LessonSummary } from '../api'
import { LibraryView } from './LibraryScreen'

function summary(overrides: Partial<LessonSummary>): LessonSummary {
  return {
    id: 'sample',
    title: 'Projectile motion',
    subject: 'physics',
    status: 'ready',
    current_stage: null,
    created: '2026-10-03T00:00:00+00:00',
    problems_total: 2,
    problems_done: 1,
    ...overrides
  }
}

function render(lessons: LessonSummary[]): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<LibraryView lessons={lessons} onOpen={() => {}} />)
  return root
}

describe('LibraryView', () => {
  it('shows one tile per lesson in order, then the new lesson tile last', () => {
    const root = render([summary({ id: 'a', title: 'First' }), summary({ id: 'b', title: 'Second' })])
    const titles = [...root.querySelectorAll('.tile-title')].map((e) => e.textContent)
    expect(titles).toEqual(['First', 'Second', 'New lesson'])
  })

  it('shows only the new lesson tile when there are no lessons', () => {
    const tiles = render([]).querySelectorAll('.tile')
    expect(tiles).toHaveLength(1)
    expect(tiles[0].textContent).toBe('New lesson')
  })

  it('shows problem progress on ready lessons', () => {
    const root = render([summary({})])
    expect(root.textContent).toContain('1 of 2 problems done')
    expect(root.querySelector('.progress-fill')?.getAttribute('style')).toContain('width:50%')
  })

  it('shows status instead of progress, and cannot be opened, while not ready', () => {
    const root = render([summary({ status: 'generating' }), summary({ id: 'f', status: 'failed' })])
    const [generating, failed] = root.querySelectorAll<HTMLButtonElement>('.tile')
    expect(generating.textContent).toContain('Generating')
    expect(failed.textContent).toContain('Generation failed')
    expect(generating.disabled && failed.disabled).toBe(true)
    expect(root.querySelector('.progress-bar')).toBeNull()
  })
})

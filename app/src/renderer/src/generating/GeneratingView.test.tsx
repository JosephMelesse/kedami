import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { LessonResponse } from '../api'
import { GeneratingView } from './GeneratingScreen'

function status(overrides: Partial<LessonResponse>): LessonResponse {
  return { lesson: null, status: 'generating', current_stage: null, error: null, materials: [], rerun_stages: [], ...overrides }
}

function render(value: LessonResponse | null, error: string | null = null): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<GeneratingView status={value} error={error} onRerun={() => {}} />)
  return root
}

const stages = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>('.stage')].map((e) => e.dataset.state)

describe('GeneratingView', () => {
  it('marks stages before the current one done', () => {
    const root = render(status({ current_stage: 3 }))
    expect(stages(root)).toEqual(['done', 'done', 'current', 'pending'])
    expect(root.querySelector('h1')?.textContent).toBe('Generating your lesson')
  })

  it('shows every stage pending before the first one starts', () => {
    expect(stages(render(status({})))).toEqual(['pending', 'pending', 'pending', 'pending'])
  })

  it('shows the failed stage and the reason', () => {
    const root = render(status({ status: 'failed', current_stage: 4, error: 'Section 2 failed after 3 attempts.' }))
    expect(stages(root)).toEqual(['done', 'done', 'done', 'failed'])
    expect(root.querySelector('h1')?.textContent).toBe('Generation failed')
    expect(root.textContent).toContain('Section 2 failed after 3 attempts.')
  })

  it('offers a rerun only for a failed lesson that can be rerun', () => {
    const rerun = (s: LessonResponse) => render(s).textContent?.includes('Rerun')
    expect(rerun(status({ status: 'failed', current_stage: 2, rerun_stages: [1, 2] }))).toBe(true)
    expect(rerun(status({ status: 'failed', current_stage: 2, rerun_stages: [] }))).toBe(false)
    expect(rerun(status({ current_stage: 2, rerun_stages: [1, 2] }))).toBe(false)
  })
})

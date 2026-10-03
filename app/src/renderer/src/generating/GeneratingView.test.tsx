import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { LessonResponse } from '../api'
import { GeneratingView } from './GeneratingScreen'

function render(status: LessonResponse | null, error: string | null = null): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<GeneratingView status={status} error={error} />)
  return root
}

const stages = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>('.stage')].map((e) => e.dataset.state)

describe('GeneratingView', () => {
  it('marks stages before the current one done', () => {
    const root = render({ lesson: null, status: 'generating', current_stage: 3, error: null })
    expect(stages(root)).toEqual(['done', 'current', 'pending'])
    expect(root.querySelector('h1')?.textContent).toBe('Generating your lesson')
  })

  it('shows every stage pending before the first one starts', () => {
    expect(stages(render({ lesson: null, status: 'generating', current_stage: null, error: null }))).toEqual([
      'pending',
      'pending',
      'pending'
    ])
  })

  it('shows the failed stage and the reason', () => {
    const root = render({ lesson: null, status: 'failed', current_stage: 4, error: 'Section 2 failed after 3 attempts.' })
    expect(stages(root)).toEqual(['done', 'done', 'failed'])
    expect(root.querySelector('h1')?.textContent).toBe('Generation failed')
    expect(root.textContent).toContain('Section 2 failed after 3 attempts.')
  })
})

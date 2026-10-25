import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { LessonResponse } from '../api'
import { GeneratingView } from './GeneratingScreen'

function status(overrides: Partial<LessonResponse>): LessonResponse {
  return { lesson: null, builder: 'agent', status: 'generating', current_stage: null, error: null, materials: [], reading_block: null, day_starts: [], ...overrides }
}

function render(value: LessonResponse | null, error: string | null = null): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<GeneratingView status={value} error={error} onCancel={() => {}} />)
  return root
}

const stages = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>('.stage')].map((e) => e.dataset.state)

describe('GeneratingView', () => {
  it('marks stages before the current one done', () => {
    const root = render(status({ current_stage: 3 }))
    expect(stages(root)).toEqual(['done', 'done', 'current', 'pending'])
    expect(root.querySelector('h1')?.textContent).toBe('Generating your lesson')
  })

  it('shows the game below the stages while generating, and not once failed', () => {
    const root = render(status({ current_stage: 2 }))
    const game = root.querySelector('.game')
    expect(game).not.toBeNull()
    expect(root.querySelector('.stages')!.compareDocumentPosition(game!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(render(status({ status: 'failed', current_stage: 2 })).querySelector('.game')).toBeNull()
    expect(render(null).querySelector('.game')).toBeNull()
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

  it('shows an agent lesson waiting for Claude Code with the command to run', () => {
    const root = render(status({}))
    expect(root.querySelector('h1')?.textContent).toBe('Waiting for Claude Code')
    expect(root.querySelector('code')?.textContent).toBe('/kedami:lesson')
  })

  it('shows an agent lesson Claude Code has started like any other', () => {
    const root = render(status({ current_stage: 2 }))
    expect(root.querySelector('h1')?.textContent).toBe('Generating your lesson')
    expect(stages(root)).toEqual(['done', 'current', 'pending', 'pending'])
    expect(root.textContent).toContain('Claude Code is building it')
  })

  it('offers Cancel while Claude Code is building, and no Rerun once failed', () => {
    const buttons = (s: LessonResponse) => [...render(s).querySelectorAll('button')].map((b) => b.textContent)
    expect(buttons(status({}))).toContain('Cancel')
    expect(buttons(status({ current_stage: 3 }))).toContain('Cancel')
    expect(buttons(status({ status: 'failed', current_stage: 3, error: 'Canceled.' }))).toEqual([])
  })
})

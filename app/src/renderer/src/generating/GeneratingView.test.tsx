import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { buildIsWaiting, type Job, type JobQueue, type LessonResponse } from '../api'
import { GeneratingView } from './GeneratingScreen'

function status(overrides: Partial<LessonResponse>): LessonResponse {
  return { lesson: null, builder: 'agent', status: 'generating', current_stage: null, error: null, materials: [], reading_block: null, day_starts: [], ...overrides }
}

function render(value: LessonResponse | null, error: string | null = null, behind = false): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<GeneratingView status={value} behind={behind} error={error} onCancel={() => {}} />)
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

  it('shows Claude Code starting before the first step, with nothing to type', () => {
    const root = render(status({}))
    expect(root.querySelector('h1')?.textContent).toBe('Starting Claude Code')
    expect(root.textContent).toContain('Claude Code is building it')
    expect(root.querySelector('code')).toBeNull()
  })

  it('says when the build is waiting behind another job, and stops saying so once it starts', () => {
    const root = render(status({}), null, true)
    expect(root.querySelector('h1')?.textContent).toBe('Waiting for another job')
    expect(root.textContent).toContain('starts as soon as it finishes')
    expect(render(status({ current_stage: 1 }), null, true).querySelector('h1')?.textContent).toBe('Generating your lesson')
  })

  it("shows the reason a build job failed, such as Claude Code's login", () => {
    const root = render(status({ status: 'failed', error: 'Invalid API key. Please run /login' }), null, true)
    expect(root.querySelector('h1')?.textContent).toBe('Generation failed')
    expect(root.textContent).toContain('Please run /login')
  })

  it('shows a lesson Claude Code has started like any other', () => {
    const root = render(status({ current_stage: 2 }))
    expect(root.querySelector('h1')?.textContent).toBe('Generating your lesson')
    expect(stages(root)).toEqual(['done', 'current', 'pending', 'pending'])
    expect(root.textContent).toContain('Claude Code is building it')
  })

  it('offers Cancel while Claude Code is starting or building, and no Rerun once failed', () => {
    const buttons = (s: LessonResponse) => [...render(s).querySelectorAll('button')].map((b) => b.textContent)
    expect(buttons(status({}))).toContain('Cancel')
    expect(buttons(status({ current_stage: 3 }))).toContain('Cancel')
    expect(buttons(status({ status: 'failed', current_stage: 3, error: 'Canceled.' }))).toEqual([])
  })
})

describe('buildIsWaiting', () => {
  const job = (overrides: Partial<Job>): Job => ({
    id: 1, kind: 'build', lesson_id: 'mine', block_id: null, part_id: null, status: 'queued', error: null, ...overrides
  })
  const queue = (running: Job | null, queued: Job[]): JobQueue => ({ claude: true, running, queued })

  it("is true only while this lesson's build is queued behind a running job", () => {
    const other = job({ id: 2, kind: 'solution', lesson_id: 'other', status: 'running' })
    expect(buildIsWaiting(queue(other, [job({})]), 'mine')).toBe(true)
    expect(buildIsWaiting(queue(job({ status: 'running' }), []), 'mine')).toBe(false)
    expect(buildIsWaiting(queue(other, [job({ lesson_id: 'someone-else' })]), 'mine')).toBe(false)
    expect(buildIsWaiting(queue(null, [job({})]), 'mine')).toBe(false)
    expect(buildIsWaiting(null, 'mine')).toBe(false)
  })
})

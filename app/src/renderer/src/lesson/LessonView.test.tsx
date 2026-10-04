import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import fixture from '../../../../../server/fixtures/sample-lesson.json'
import type { ProgressRecord } from '../api'
import { sanitizeSvg } from './blocks/DiagramBlockView'
import { LessonView } from './LessonView'
import { ProgressProvider } from './progress/ProgressContext'
import type { Lesson } from './types'

const lesson = fixture as unknown as Lesson

function render(value: Lesson, progress: ProgressRecord[] = []): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(
    <ProgressProvider lessonId={value.id} initial={progress}>
      <LessonView lesson={value} />
    </ProgressProvider>
  )
  return root
}

function record(part_id: string, overrides: Partial<ProgressRecord>): ProgressRecord {
  return {
    block_id: 'ps3-4',
    part_id,
    status: 'in_progress',
    last_response: null,
    attempts: 0,
    hints_used: 0,
    updated: null,
    ...overrides
  }
}

function field(root: HTMLElement, partIndex: number): HTMLElement {
  return root.querySelectorAll<HTMLElement>('.part .answer-field')[partIndex]
}

function text(root: HTMLElement): string {
  return root.textContent ?? ''
}

describe('LessonView with the sample lesson', () => {
  const root = render(lesson)

  it('renders the title and every section', () => {
    expect(root.querySelector('h1')?.textContent).toBe('Projectile motion')
    expect([...root.querySelectorAll('h2')].map((h) => h.textContent)).toEqual([
      'Components of velocity',
      'Motion under gravity'
    ])
  })

  it('renders math with KaTeX, including display math', () => {
    expect(root.querySelectorAll('.katex').length).toBeGreaterThan(10)
    expect(root.querySelectorAll('.katex-display').length).toBe(3)
  })

  it('shows a part count only on the multi-part problem', () => {
    expect([...root.querySelectorAll('.part-count')].map((e) => e.textContent)).toEqual(['0 of 4 parts done'])
  })

  it('labels each part of a multi-part problem', () => {
    expect([...root.querySelectorAll('.part-label')].map((e) => e.textContent)).toEqual(['(a)', '(b)', '(c)', '(d)'])
  })

  it('marks unverified answers, but never self checks', () => {
    // The expression checkpoint and part (c); part (d) is a self check with no verified flag.
    expect(text(root).match(/Unverified answer/g)).toHaveLength(2)
  })

  it('shows the unit beside numeric inputs', () => {
    expect([...root.querySelectorAll('.unit')].map((e) => e.textContent)).toEqual(['m/s', 's', 'm'])
  })

  it('renders an input for each answer kind', () => {
    expect(root.querySelectorAll('input[type=radio]').length).toBe(4)
    expect(root.querySelectorAll('input[type=checkbox]').length).toBe(4)
    expect(root.querySelectorAll('input[type=text]').length).toBe(5)
    expect(text(root)).toContain('Show rubric')
  })

  it('starts with no progress, no state labels, and a parameter slider', () => {
    expect(text(root)).toContain('0 of 2 problems done')
    expect(root.querySelectorAll('.state-label')).toHaveLength(0)
    expect(root.querySelectorAll('input[type=range]')).toHaveLength(1)
  })

  it('offers hints and mark done on problem parts, but no mark done on checkpoints', () => {
    expect(text(field(root, 0))).toContain('Show hint 1 of 2')
    expect(text(field(root, 0))).toContain('Mark done')
    const checkpoint = root.querySelector<HTMLElement>('.card .answer-field')!
    expect(text(checkpoint)).toContain('Show hint 1 of 2')
    expect(text(checkpoint)).not.toContain('Mark done')
  })

  it('offers a solution under every problem part, and none on checkpoints', () => {
    const parts = lesson.sections.flatMap((s) => s.blocks).flatMap((b) => (b.type === 'problem' ? b.parts : []))
    const buttons = [...root.querySelectorAll('.solution button')].map((b) => b.textContent)
    expect(buttons).toEqual(parts.map(() => 'Show solution'))
    const checkpoint = root.querySelector<HTMLElement>('.card .answer-field')!.closest('.card')!
    expect(checkpoint.querySelector('.solution')).toBeNull()
    expect(root.querySelector('.solution-steps')).toBeNull()
  })

  it('starts worked examples with no steps revealed', () => {
    expect(root.querySelector('.steps')).toBeNull()
    expect(text(root)).toContain('Show step 1 of 4')
  })

  it('never renders stored answers, hints, or rubrics', () => {
    expect(text(root)).not.toContain('32.559')
    expect(text(root)).not.toContain('The horizontal component uses cosine')
    expect(text(root)).not.toContain('complementary angles')
  })
})

describe('LessonView with saved progress', () => {
  const root = render(lesson, [
    record('a', { status: 'correct', last_response: '2.36', attempts: 2 }),
    record('b', { last_response: '30', attempts: 1, hints_used: 1 }),
    record('c', { hints_used: 2 }),
    record('d', { status: 'marked_done' }),
    { ...record('5', { status: 'marked_done' }), block_id: 'ps3-5' }
  ])

  it('labels each state and colors only the answer field border', () => {
    const states = [0, 1, 2, 3].map((i) => field(root, i).dataset.state)
    expect(states).toEqual(['correct', 'wrong', 'in_progress', 'marked_done'])
    const labels = [0, 1, 2, 3].map((i) => field(root, i).querySelector('.state-label')?.textContent)
    expect(labels).toEqual(['Correct', 'In progress', 'In progress', 'Marked done'])
  })

  it('counts parts and problems', () => {
    expect(root.querySelector('.part-count')?.textContent).toBe('2 of 4 parts done')
    expect(text(root)).toContain('1 of 2 problems done')
  })

  it('locks a correct part and restores its answer, with no hint or mark done', () => {
    const input = field(root, 0).querySelector('input')!
    expect(input.disabled).toBe(true)
    expect(input.value).toBe('2.36')
    expect(field(root, 0).querySelector('button')).toBeNull()
  })

  it('keeps a wrong answer editable with the last response restored', () => {
    const input = field(root, 1).querySelector('input')!
    expect(input.disabled).toBe(false)
    expect(input.value).toBe('30')
  })

  it('shows revealed hints and offers the next one', () => {
    expect(field(root, 1).querySelectorAll('.hints li')).toHaveLength(1)
    expect(text(field(root, 1))).toContain('Show hint 2 of 2')
    expect(field(root, 2).querySelectorAll('.hints li')).toHaveLength(2)
    expect(text(field(root, 2))).not.toContain('Show hint')
  })

  it('offers undo on a marked part', () => {
    expect(text(field(root, 3))).toContain('Undo mark done')
    expect(field(root, 3).querySelector('textarea')?.disabled).toBe(true)
  })

  it('says the lesson is complete when every problem is done', () => {
    const all = render(lesson, [
      ...['a', 'b', 'c', 'd'].map((p) => record(p, { status: 'marked_done' })),
      { ...record('5', { status: 'correct' }), block_id: 'ps3-5' }
    ])
    expect(text(all)).toContain('Lesson complete')
  })
})

describe('LessonView captions', () => {
  it('renders math in plot and diagram captions', () => {
    const withMath = structuredClone(lesson)
    const plot = withMath.sections[1].blocks.find((b) => b.type === 'plot')!
    if (plot.type === 'plot') plot.caption = 'Height as the angle $\\theta$ changes.'
    const caption = [...render(withMath).querySelectorAll('figcaption')].find((f) => f.textContent?.includes('Height as'))!
    expect(caption.querySelector('.katex')).not.toBeNull()
    expect(caption.textContent).not.toContain('$')
  })
})

describe('LessonView edge cases', () => {
  it('renders a simulation card that loads its code separately', () => {
    const withSimulation = structuredClone(lesson)
    withSimulation.sections[0].blocks.push({ type: 'simulation', id: 'sim', code: 'SECRET_CODE()', caption: 'Drag $A$.', brief: null })
    const card = render(withSimulation).querySelector<HTMLElement>('.simulation')!
    expect(card.querySelector('figcaption .katex')).not.toBeNull()
    expect(text(card)).toContain('Loading simulation')
    expect(text(card)).toContain('Regenerate')
    expect(card.innerHTML).not.toContain('SECRET_CODE')
  })

  it('does not render raw HTML from Markdown', () => {
    const withHtml = structuredClone(lesson)
    withHtml.sections[0].blocks[0] = { type: 'explanation', id: 'x', body: 'Hi <img src=x onerror="alert(1)"> there' }
    expect(render(withHtml).querySelector('img')).toBeNull()
  })
})

describe('sanitizeSvg', () => {
  it('keeps drawing elements', () => {
    const clean = sanitizeSvg('<svg viewBox="0 0 10 10"><line x1="0" y1="0" x2="10" y2="10" stroke="currentColor"/></svg>')
    expect(clean).toContain('<line')
  })

  it('removes scripts, handlers, styles, and foreign content', () => {
    const clean = sanitizeSvg(
      '<svg onload="alert(1)"><script>alert(2)</script><style>body{display:none}</style>' +
        '<foreignObject><div>html</div></foreignObject><a href="javascript:alert(3)"><text>t</text></a></svg>'
    )
    expect(clean).not.toMatch(/onload|<script|<style|foreignObject|javascript:/i)
  })
})

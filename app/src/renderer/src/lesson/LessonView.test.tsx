import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import fixture from '../../../../../server/fixtures/sample-lesson.json'
import { sanitizeSvg } from './blocks/DiagramBlockView'
import { LessonView } from './LessonView'
import type { Lesson } from './types'

const lesson = fixture as unknown as Lesson

function render(value: Lesson): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<LessonView lesson={value} />)
  return root
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

describe('LessonView edge cases', () => {
  it('renders nothing for a simulation block', () => {
    const withSimulation = structuredClone(lesson)
    withSimulation.sections[0].blocks.push({ type: 'simulation', id: 'sim', code: 'draw()', caption: 'SIM CAPTION' })
    expect(text(render(withSimulation))).not.toContain('SIM CAPTION')
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

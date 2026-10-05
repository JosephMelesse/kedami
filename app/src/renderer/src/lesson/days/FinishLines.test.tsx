import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import fixture from '../../../../../../server/fixtures/sample-lesson.json'
import type { KedamiApi } from '../../../../preload/api'
import { LessonView } from '../LessonView'
import { ProgressProvider } from '../progress/ProgressContext'
import type { Lesson } from '../types'
import { type DayBar, DayBarProvider, useDayBar } from './DayBar'
import { boundaries, NOTE_MS } from './days'

// Blocks: components-intro, -diagram, -example, -check, then gravity-intro (first in section 2),
// height-plot, angle-plot, apex-check, height-expression-check, ps3-4, ps3-5.
const lesson = fixture as unknown as Lesson
const HEADER = 56
const WINDOW = 768
// Each block sits 300px below the one before it and is 250px tall, so the lesson ends at 3250.
const BLOCK_STEP = 300
const BLOCK_HEIGHT = 250
const END = 10 * BLOCK_STEP + BLOCK_HEIGHT
// A finish line sits in the gap above the block after it, ending 20px above that block.
const LINE_GAP = 20
// A section starts 80px above its first block, where its heading is.
const HEADING = 80

let container: HTMLDivElement
let root: Root
let realRect: () => DOMRect
let bar: DayBar | null

function setScroll(y: number) {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true })
}

function scrollPage(y: number) {
  setScroll(y)
  window.dispatchEvent(new Event('scroll'))
}

/** The page top of the block at `index`, measured from the top of the lesson. */
const blockTop = (index: number) => index * BLOCK_STEP
/** The page bottom of the line before the block at `index`. */
const lineBottom = (index: number) => blockTop(index) - LINE_GAP

beforeEach(() => {
  vi.useFakeTimers()
  setScroll(0)
  Object.defineProperty(window, 'innerHeight', { value: WINDOW, configurable: true })
  container = document.createElement('div')
  const header = document.createElement('header')
  header.className = 'app-header'
  container.append(header)
  document.body.append(container)
  root = createRoot(container.appendChild(document.createElement('div')))

  realRect = Element.prototype.getBoundingClientRect
  Element.prototype.getBoundingClientRect = function (this: Element) {
    if (this.classList.contains('app-header')) return { top: 0, bottom: HEADER } as DOMRect
    const blocks = [...document.querySelectorAll('[data-block-id]')]
    const at = (top: number, height: number) => ({ top: top - window.scrollY, bottom: top + height - window.scrollY })
    if (blocks.includes(this)) return at(blockTop(blocks.indexOf(this)), BLOCK_HEIGHT) as DOMRect
    if (this.classList.contains('lesson-section')) {
      return at(blockTop(blocks.indexOf(this.querySelector('[data-block-id]')!)) - HEADING, 0) as DOMRect
    }
    if (this.hasAttribute('data-finish-line')) {
      // Measured from the block after it, which follows it in page order.
      const next = blocks.findIndex((block) => this.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING)
      return at(lineBottom(next) - 20, 20) as DOMRect
    }
    return realRect.call(this)
  }
  // Jumping to the reading position moves the page.
  window.scrollTo = ((options: ScrollToOptions) => setScroll(options.top ?? 0)) as typeof window.scrollTo

  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/points') ? { functions: [] } : {})))
  )
  bar = null
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  Element.prototype.getBoundingClientRect = realRect
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function Probe() {
  bar = useDayBar()
  return null
}

async function open(dayStarts: string[], readingBlock: string | null = null, shown = true) {
  await act(async () =>
    root.render(
      <DayBarProvider>
        <Probe />
        {shown && (
          <ProgressProvider lessonId={lesson.id} initial={[]}>
            <LessonView lesson={lesson} readingBlock={readingBlock} dayStarts={dayStarts} />
          </ProgressProvider>
        )}
      </DayBarProvider>
    )
  )
}

async function scroll(y: number) {
  await act(async () => scrollPage(y))
}

async function wait(ms: number) {
  await act(async () => vi.advanceTimersByTimeAsync(ms))
}

/** Scroll so the bottom of the window is at `point`. */
const reading = (point: number) => scroll(point - WINDOW)

describe('Finish lines', () => {
  it('draws a labeled line above the section or block that starts each day', async () => {
    await open(['gravity-intro', 'apex-check'])
    const lines = [...container.querySelectorAll('[data-finish-line]')]
    expect(lines.map((line) => line.textContent)).toEqual(['End of day 1', 'End of day 2'])
    // A day that starts a section ends above its heading, between the sections.
    const sections = container.querySelectorAll('.lesson-section')
    expect(lines[0].nextElementSibling).toBe(sections[1])
    expect(lines[1].nextElementSibling?.getAttribute('data-block-id')).toBe('apex-check')
  })

  it('draws no lines in a lesson that is not split', async () => {
    await open([])
    expect(container.querySelector('[data-finish-line]')).toBeNull()
  })

  it('fills toward the next line, as far as the bottom of the window has come', async () => {
    await open(['gravity-intro'])
    expect(bar).toEqual({ fill: WINDOW / lineBottom(4), note: false })
    await reading(lineBottom(4) / 2)
    expect(bar).toEqual({ fill: 0.5, note: false })
  })

  it('fills toward the end of a lesson with no lines, and shows no note there', async () => {
    await open([])
    await reading(END / 2)
    expect(bar).toEqual({ fill: 0.5, note: false })
    await reading(END)
    expect(bar).toEqual({ fill: 1, note: false })
    await wait(NOTE_MS)
    expect(bar).toEqual({ fill: 1, note: false })
  })

  it('shows Done for today for 4 seconds on passing a line, then starts the next day empty', async () => {
    await open(['gravity-intro'])
    await reading(lineBottom(4))
    expect(bar).toEqual({ fill: 1, note: true })
    await wait(NOTE_MS - 1)
    expect(bar).toEqual({ fill: 1, note: true })
    await wait(1)
    expect(bar).toEqual({ fill: 0, note: false })
  })

  it('shows one note for several lines passed at once, including the end of a split lesson', async () => {
    await open(['gravity-intro', 'apex-check'])
    await reading(END)
    expect(bar).toEqual({ fill: 1, note: true })
    await wait(NOTE_MS)
    expect(bar).toEqual({ fill: 1, note: false })
  })

  it('shows no note on scrolling back up across a line, and one again on passing it again', async () => {
    await open(['gravity-intro'])
    await reading(lineBottom(4) + 100)
    await wait(NOTE_MS)
    await reading(lineBottom(4) - 100)
    expect(bar?.note).toBe(false)
    await reading(lineBottom(4))
    expect(bar?.note).toBe(true)
  })

  it('shows no note when the lesson opens past a line', async () => {
    await open(['gravity-intro'], 'apex-check')
    expect(window.scrollY).toBe(blockTop(7) - HEADER)
    // Day 2 runs from the line to the end of the lesson.
    const point = window.scrollY + WINDOW
    expect(bar).toEqual({ fill: (point - lineBottom(4)) / (END - lineBottom(4)), note: false })
    // The scroll from the jump arrives after it and changes nothing.
    await scroll(window.scrollY)
    expect(bar?.note).toBe(false)
  })

  it('shows no note when the lesson is split again', async () => {
    await open(['apex-check'])
    await reading(lineBottom(4) + 10)
    await open(['gravity-intro'])
    expect(bar?.note).toBe(false)
  })

  it('clears the bar when the lesson closes', async () => {
    await open(['gravity-intro'])
    await reading(lineBottom(4))
    await open(['gravity-intro'], null, false)
    expect(bar).toBeNull()
    await wait(NOTE_MS)
    expect(bar).toBeNull()
  })

  it('measures a block that opens its section from the section heading', async () => {
    await open([])
    const measured = boundaries(container)
    expect(measured.slice(3, 6)).toEqual([
      { id: 'components-check', top: blockTop(3) },
      { id: 'gravity-intro', top: blockTop(4) - HEADING },
      { id: 'height-plot', top: blockTop(5) }
    ])
    expect(measured[0]).toEqual({ id: 'components-intro', top: -HEADING })
  })
})

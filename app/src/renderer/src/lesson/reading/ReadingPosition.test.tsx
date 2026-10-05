import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import fixture from '../../../../../../server/fixtures/sample-lesson.json'
import type { KedamiApi } from '../../../../preload/api'
import { LessonView } from '../LessonView'
import { ProgressProvider } from '../progress/ProgressContext'
import type { Lesson } from '../types'

const lesson = fixture as unknown as Lesson
const HEADER = 56
// Each block sits 300px below the one before it and is 250px tall.
const BLOCK_STEP = 300
const BLOCK_HEIGHT = 250

let container: HTMLDivElement
let root: Root
let fetchMock: Mock
let scrollTo: Mock
let realRect: () => DOMRect

function setScroll(y: number) {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true })
}

function scrollPage(y: number) {
  setScroll(y)
  window.dispatchEvent(new Event('scroll'))
}

beforeEach(() => {
  vi.useFakeTimers()
  setScroll(0)
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
    const index = blocks.indexOf(this)
    if (index < 0) return realRect.call(this)
    const top = index * BLOCK_STEP - window.scrollY
    return { top, bottom: top + BLOCK_HEIGHT } as DOMRect
  }
  scrollTo = vi.fn()
  window.scrollTo = scrollTo as unknown as typeof window.scrollTo

  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  fetchMock = vi.fn(async (url: string) =>
    new Response(JSON.stringify(url.endsWith('/points') ? { functions: [] } : { block_id: 'x' }))
  )
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  Element.prototype.getBoundingClientRect = realRect
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

async function open(readingBlock: string | null) {
  await act(async () =>
    root.render(
      <ProgressProvider lessonId={lesson.id} initial={[]}>
        <LessonView lesson={lesson} readingBlock={readingBlock} />
      </ProgressProvider>
    )
  )
}

async function wait(ms: number) {
  await act(async () => vi.advanceTimersByTimeAsync(ms))
}

const saved = () =>
  fetchMock.mock.calls
    .filter(([url]) => String(url).endsWith('/reading-position'))
    .map(([, init]) => JSON.parse(init.body).block_id)

describe('Reading position', () => {
  it('opens at the saved block, its top just below the header', async () => {
    await open('gravity-intro')
    expect(scrollTo).toHaveBeenCalledWith({ top: 4 * BLOCK_STEP - HEADER, behavior: 'instant' })
  })

  it('opens at the top with no saved block, or one gone after a rerun', async () => {
    await open(null)
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: 'instant' })
    await act(async () => root.unmount())
    root = createRoot(container.appendChild(document.createElement('div')))
    await open('removed-block-9')
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: 'instant' })
  })

  it('saves the block being read once scrolling has stopped for a second', async () => {
    await open(null)
    scrollPage(400)
    await wait(500)
    scrollPage(1000)
    await wait(999)
    expect(saved()).toEqual([])
    await wait(1)
    // Block 3 spans 900 to 1150, so 150px of it is still below the 56px header.
    expect(saved()).toEqual(['components-check'])
    const [url, init] = fetchMock.mock.calls.find(([u]) => String(u).endsWith('/reading-position'))!
    expect([url, init.method]).toEqual([`http://127.0.0.1:1/lessons/${lesson.id}/reading-position`, 'POST'])
  })

  it('saves nothing when the block has not changed', async () => {
    await open('components-check')
    scrollPage(1000)
    await wait(2000)
    scrollPage(1010)
    await wait(2000)
    expect(saved()).toEqual([])
  })

  it('saves each change once', async () => {
    await open(null)
    scrollPage(1000)
    await wait(1000)
    scrollPage(1010)
    await wait(1000)
    scrollPage(1300)
    await wait(1000)
    expect(saved()).toEqual(['components-check', 'gravity-intro'])
  })

  it('saves at once on leaving the lesson, and not again after', async () => {
    await open(null)
    scrollPage(1300)
    await act(async () => root.unmount())
    await wait(0)
    expect(saved()).toEqual(['gravity-intro'])
    await wait(2000)
    expect(saved()).toEqual(['gravity-intro'])
  })

  it('saves nothing on leaving without scrolling', async () => {
    await open('gravity-intro')
    await act(async () => root.unmount())
    await wait(2000)
    expect(saved()).toEqual([])
  })

  it('keeps working when a save fails', async () => {
    await open(null)
    fetchMock.mockImplementation(async () => new Response(JSON.stringify({ detail: 'down' }), { status: 500 }))
    scrollPage(1000)
    await wait(1000)
    scrollPage(1300)
    await wait(1000)
    expect(saved()).toEqual(['components-check', 'gravity-intro'])
  })
})

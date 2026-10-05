import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import fixture from '../../../../../../server/fixtures/sample-lesson.json'
import type { KedamiApi } from '../../../../preload/api'
import { LessonScreen } from '../LessonScreen'
import { DayBarProvider } from './DayBar'

// Blocks sit 300px apart and are 250px tall, so the lesson's blocks end at 3250. A section starts
// 80px above its first block, so the lesson starts at -80 and section 2 (gravity-intro, block 4) at 1120.
const BLOCK_STEP = 300
const BLOCK_HEIGHT = 250
const HEADING = 80

let container: HTMLDivElement
let root: Root
let fetchMock: Mock
let realRect: () => DOMRect
let dayStarts: string[]

beforeEach(() => {
  Object.defineProperty(window, 'scrollY', { value: 0, configurable: true })
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true
  }
  window.scrollTo = (() => {}) as typeof window.scrollTo

  realRect = Element.prototype.getBoundingClientRect
  Element.prototype.getBoundingClientRect = function (this: Element) {
    const blocks = [...document.querySelectorAll('[data-block-id]')]
    if (blocks.includes(this)) {
      const top = blocks.indexOf(this) * BLOCK_STEP
      return { top, bottom: top + BLOCK_HEIGHT } as DOMRect
    }
    if (this.classList.contains('lesson-section')) {
      const top = blocks.indexOf(this.querySelector('[data-block-id]')!) * BLOCK_STEP - HEADING
      return { top, bottom: top } as DOMRect
    }
    return realRect.call(this)
  }

  dayStarts = []
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
    if (url.endsWith('/days')) return json({ block_ids: JSON.parse(String(init!.body)).block_ids })
    if (url.endsWith('/progress')) return json({ progress: [] })
    if (url.endsWith('/points')) return json({ functions: [] })
    return json({
      lesson: fixture,
      status: 'ready',
      current_stage: null,
      error: null,
      materials: [],
      rerun_stages: [],
      reading_block: null,
      day_starts: dayStarts
    })
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  Element.prototype.getBoundingClientRect = realRect
  vi.unstubAllGlobals()
})

async function open() {
  await act(async () =>
    root.render(
      <DayBarProvider>
        <LessonScreen lessonId={fixture.id} onBack={() => {}} onRerun={() => {}} />
      </DayBarProvider>
    )
  )
}

const button = (label: string) => [...container.querySelectorAll('button')].find((b) => b.textContent === label)!
const input = () => container.querySelector<HTMLInputElement>('dialog input')!
const lines = () => [...container.querySelectorAll('[data-finish-line]')].map((line) => line.textContent)
const saved = () =>
  fetchMock.mock.calls
    .filter(([url]) => String(url).endsWith('/days'))
    .map(([, init]) => JSON.parse(init.body).block_ids)

async function enter(text: string) {
  await act(async () => {
    // React tracks the value through the prototype's setter.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input(), text)
    input().dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function split(days: string) {
  await act(async () => button('Days').click())
  await enter(days)
  await act(async () => button('Split').click())
}

describe('Days', () => {
  it('opens with the current number of days, up to the number of blocks', async () => {
    dayStarts = ['gravity-intro']
    await open()
    await act(async () => button('Days').click())
    expect(input().value).toBe('2')
    expect(container.querySelector('dialog .field-label')!.textContent).toBe('Days, 1 to 11')
  })

  it('accepts only a whole number of days from 1 to the most allowed', async () => {
    await open()
    await act(async () => button('Days').click())
    for (const text of ['', '0', '12', '2.5', '-1', 'two']) {
      await enter(text)
      expect([text, button('Split').disabled]).toEqual([text, true])
    }
    await enter(' 11 ')
    expect(button('Split').disabled).toBe(false)
  })

  it('cuts at the boundaries nearest to equal heights, saves them, and draws the lines', async () => {
    await open()
    // -80 to 3250 in three days: targets at 1030 and 2140, nearest section 2 at 1120 and apex-check at 2100.
    await split('3')
    expect(saved()).toEqual([['gravity-intro', 'apex-check']])
    expect(lines()).toEqual(['End of day 1', 'End of day 2'])
    expect(container.querySelector('dialog')).toBeNull()
  })

  it('removes the lines with 1 day', async () => {
    dayStarts = ['gravity-intro']
    await open()
    expect(lines()).toEqual(['End of day 1'])
    await split('1')
    expect(saved()).toEqual([[]])
    expect(lines()).toEqual([])
  })

  it('keeps the dialog open with the reason when saving fails', async () => {
    await open()
    fetchMock.mockImplementationOnce(async () => new Response(JSON.stringify({ detail: 'Nope.' }), { status: 422 }))
    await split('2')
    expect(container.querySelector('dialog .answer-error')?.textContent).toBe('Nope.')
    expect(lines()).toEqual([])
  })
})

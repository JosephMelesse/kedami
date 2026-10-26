import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KedamiApi } from '../../../../preload/api'
import type { Selection } from '../../api'
import { SectionView } from '../SectionView'
import type { Section } from '../types'
import { SelectionProvider } from './Selection'

const SECTION: Section = {
  id: 'vectors',
  title: 'Vectors',
  goal: 'Split a velocity into components.',
  blocks: [
    { type: 'explanation', id: 'vectors-block-1', body: 'A vector has a size and a direction.' },
    { type: 'explanation', id: 'vectors-block-2', body: 'Its components add back up to it.' }
  ]
}

// The stand-in server's one selection, the bodies posted to it, and whether it refuses the next post.
let stored: Selection | null
let posted: unknown[]
let refuseNext: boolean
let container: HTMLDivElement
let root: Root

beforeEach(() => {
  stored = null
  posted = []
  refuseNext = false
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      if (new URL(url).pathname !== '/selection') throw new Error(`unexpected ${url}`)
      if (init.method === 'POST') {
        const body = JSON.parse(init.body as string)
        posted.push(body)
        if (refuseNext) {
          refuseNext = false
          return new Response(JSON.stringify({ detail: 'That block isn’t in this lesson.' }), { status: 422 })
        }
        stored = body
      }
      return new Response(JSON.stringify({ selection: stored }))
    })
  )
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

async function mount(lessonId = 'l1') {
  await act(async () =>
    root.render(
      <SelectionProvider lessonId={lessonId}>
        <SectionView section={SECTION} lessonId={lessonId} />
      </SelectionProvider>
    )
  )
}

const controls = () => [...container.querySelectorAll<HTMLButtonElement>('.select-control')]
const blockControl = (id: string) => container.querySelector<HTMLButtonElement>(`[data-block-id="${id}"] > .select-control`)!
const sectionControl = () => container.querySelector<HTMLButtonElement>('.lesson-section > header > .select-control')!
const selectedBlocks = () =>
  [...container.querySelectorAll<HTMLElement>('[data-block-id][data-selected="true"]')].map((e) => e.dataset.blockId)
const sectionSelected = () => container.querySelector('.lesson-section')?.getAttribute('data-selected') === 'true'
const click = (button: HTMLButtonElement) => act(async () => button.click())

describe('selecting a block or section for Claude Code', () => {
  it('gives every block and the section heading a Select control, with nothing selected', async () => {
    await mount()
    expect(controls()).toHaveLength(3)
    expect(controls().every((c) => c.textContent === 'Select' && c.getAttribute('aria-pressed') === 'false')).toBe(true)
    expect(selectedBlocks()).toEqual([])
    expect(sectionSelected()).toBe(false)
  })

  it('selects a block, then clears it when clicked again', async () => {
    await mount()
    await click(blockControl('vectors-block-2'))
    expect(posted.at(-1)).toEqual({ lesson_id: 'l1', section_id: null, block_id: 'vectors-block-2' })
    expect(selectedBlocks()).toEqual(['vectors-block-2'])
    expect(blockControl('vectors-block-2').textContent).toBe('Selected')

    await click(blockControl('vectors-block-2'))
    expect(posted.at(-1)).toBeNull()
    expect(selectedBlocks()).toEqual([])
  })

  it('keeps one selection: selecting the section replaces a block', async () => {
    await mount()
    await click(blockControl('vectors-block-1'))
    await click(sectionControl())
    expect(posted.at(-1)).toEqual({ lesson_id: 'l1', section_id: 'vectors', block_id: null })
    expect(sectionSelected()).toBe(true)
    expect(selectedBlocks()).toEqual([])
  })

  it('shows the selection the server holds, and none from another lesson', async () => {
    stored = { lesson_id: 'l1', section_id: null, block_id: 'vectors-block-1' }
    await mount()
    expect(selectedBlocks()).toEqual(['vectors-block-1'])

    await act(async () => root.unmount())
    root = createRoot(container)
    stored = { lesson_id: 'other', section_id: null, block_id: 'vectors-block-1' }
    await mount()
    expect(selectedBlocks()).toEqual([])
  })

  it('puts back what the server holds when a selection is refused', async () => {
    stored = { lesson_id: 'l1', section_id: null, block_id: 'vectors-block-1' }
    await mount()
    refuseNext = true
    await click(blockControl('vectors-block-2'))
    expect(selectedBlocks()).toEqual(['vectors-block-1'])
  })

  it('offers no Select control outside a lesson screen', async () => {
    await act(async () => root.render(<SectionView section={SECTION} lessonId="l1" />))
    expect(controls()).toEqual([])
  })
})

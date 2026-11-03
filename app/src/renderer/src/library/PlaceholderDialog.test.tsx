import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { parsePlaceholderList, type PlannedLesson } from '../api'
import { PlaceholderDialog } from './PlaceholderDialog'

vi.mock('../api', async (original) => ({
  ...(await original<typeof import('../api')>()),
  parsePlaceholderList: vi.fn()
}))

const parse = vi.mocked(parsePlaceholderList)
let container: HTMLDivElement
let root: Root
let created: PlannedLesson[][]

const button = (label: string) =>
  [...container.querySelectorAll('button')].find((b) => b.textContent === label || b.textContent?.startsWith(label))!

async function click(label: string) {
  await act(async () => button(label).click())
}

async function type(selector: string, value: string) {
  const field = container.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!
  await act(async () => {
    const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(field, value)
    field.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

beforeEach(async () => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  parse.mockReset()
  created = []
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  await act(async () =>
    root.render(
      <PlaceholderDialog
        onCancel={() => {}}
        onCreate={async (planned) => {
          created.push(planned)
          return null
        }}
      />
    )
  )
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

describe('PlaceholderDialog', () => {
  it('creates one from a name, with a date only if given', async () => {
    expect(button('Create').disabled).toBe(true)
    await type('[aria-label="Name"]', '  Week 1  ')
    await click('Create')
    expect(created).toEqual([[{ name: 'Week 1', due_date: null }]])
    await type('[aria-label="Due date (optional)"]', '2026-12-01')
    await click('Create')
    expect(created[1]).toEqual([{ name: 'Week 1', due_date: '2026-12-01' }])
  })

  it('previews a pasted list before anything is created', async () => {
    parse.mockResolvedValue({
      placeholders: [
        { name: 'Week 1', due_date: null },
        { name: 'Week 2', due_date: '2026-12-01' }
      ],
      problems: []
    })
    await click('Paste a list')
    expect(button('Create').disabled).toBe(true)
    await type('textarea', 'Week 1\nWeek 2 | 2026-12-01')
    expect(button('Create').disabled).toBe(true)
    await click('Preview')
    expect(created).toEqual([])
    expect(container.querySelector('.placeholder-preview')?.textContent).toContain('Week 2')
    expect(button('Create 2').disabled).toBe(false)
    await click('Create 2')
    expect(created[0]).toHaveLength(2)
  })

  it('names every bad line and offers nothing to create', async () => {
    parse.mockResolvedValue({
      placeholders: [],
      problems: [
        { line: 2, text: 'A | B | C', reason: 'It has more than one |.' },
        { line: 4, text: 'D |', reason: 'It has a | with no date after it.' }
      ]
    })
    await click('Paste a list')
    await type('textarea', 'x')
    await click('Preview')
    const lines = [...container.querySelectorAll('.placeholder-problems li')].map((li) => li.textContent)
    expect(lines).toEqual(['Line 2: It has more than one |.', 'Line 4: It has a | with no date after it.'])
    expect(button('Create').disabled).toBe(true)
  })

  it('needs a new preview after the text changes, so only what was seen is created', async () => {
    parse.mockResolvedValue({ placeholders: [{ name: 'Week 1', due_date: null }], problems: [] })
    await click('Paste a list')
    await type('textarea', 'Week 1')
    await click('Preview')
    expect(button('Create 1').disabled).toBe(false)
    await type('textarea', 'Week 1\nWeek 2')
    expect(container.querySelector('.placeholder-preview')).toBeNull()
    expect(button('Create').disabled).toBe(true)
  })
})

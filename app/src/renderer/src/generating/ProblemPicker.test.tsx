import { act, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { LeetCodeMatch } from '../api'
import type { Pick } from './picks'
import { ProblemPicker } from './ProblemPicker'

const PROBLEMS: LeetCodeMatch[] = [
  { number: 1, slug: 'two-sum', title: 'Two Sum', difficulty: 'Easy' },
  { number: 15, slug: '3sum', title: '3sum', difficulty: 'Medium' },
  { number: 92, slug: 'reverse-linked-list-ii', title: 'Reverse Linked List II', difficulty: 'Medium' },
  { number: 167, slug: 'two-sum-ii-input-array-is-sorted', title: 'Two Sum II Input Array Is Sorted', difficulty: 'Medium' },
  { number: 206, slug: 'reverse-linked-list', title: 'Reverse Linked List', difficulty: 'Easy' },
  { number: 1460, slug: 'make-two-arrays-equal-by-reversing-subarrays', title: 'Make Two Arrays Equal By Reversing Subarrays', difficulty: 'Easy' }
]

// Like the server's search: numbers by prefix with the exact one first, words by the starts of slug words.
async function search(query: string): Promise<{ problems: LeetCodeMatch[]; imported: boolean }> {
  searches.push(query)
  return { problems: matching(query), imported: true }
}

function matching(query: string): LeetCodeMatch[] {
  const text = query.trim().toLowerCase()
  if (/^\d+$/.test(text)) {
    return PROBLEMS.filter((p) => String(p.number).startsWith(text)).sort(
      (a, b) => Number(String(b.number) === text) - Number(String(a.number) === text) || a.number - b.number
    )
  }
  const tokens = text.match(/[a-z0-9]+/g) ?? []
  return PROBLEMS.filter((p) =>
    tokens.every((t) => p.slug.split('-').some((w) => w.startsWith(t)) || String(p.number) === t)
  ).sort((a, b) => a.slug.split('-').length - b.slug.split('-').length)
}

let container: HTMLDivElement
let root: Root
let searches: string[]
let latest: Pick[]

function Harness({ initial = [], nothingImported = false }: { initial?: Pick[]; nothingImported?: boolean }) {
  const [picks, setPicks] = useState<Pick[]>(initial)
  latest = picks
  return (
    <ProblemPicker picks={picks} onChange={setPicks} search={nothingImported ? searchNothing : search} />
  )
}

async function searchNothing(): Promise<{ problems: LeetCodeMatch[]; imported: boolean }> {
  return { problems: [], imported: false }
}

beforeEach(async () => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  searches = []
  latest = []
  await act(async () => root.render(<Harness />))
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

const input = () => container.querySelector<HTMLInputElement>('.picker-input')!
const settle = () => act(async () => new Promise((resolve) => setTimeout(resolve, 200)))

async function type(text: string) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
    setter.call(input(), text)
    input().dispatchEvent(new Event('input', { bubbles: true }))
  })
  await settle()
}

async function press(key: string) {
  await act(async () => {
    input().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
  })
  await settle()
}

async function paste(text: string) {
  await act(async () => {
    const event = new Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(event, 'clipboardData', { value: { getData: () => text } })
    input().dispatchEvent(event)
  })
  await settle()
}

const bubbles = () => [...container.querySelectorAll('.pick')].map((b) => b.firstChild!.textContent)
const matches = () => [...container.querySelectorAll('.picker-match')].map((m) => m.firstChild!.textContent)
const message = () => container.querySelector('.answer-error')?.textContent ?? null

describe('searching', () => {
  it('shows matches for a number or words as they are typed', async () => {
    await type('1')
    expect(matches()).toEqual(['#1 Two Sum', '#15 3sum', '#167 Two Sum II Input Array Is Sorted', '#1460 Make Two Arrays Equal By Reversing Subarrays'])
    await type('reverse linked')
    expect(matches()).toEqual(['#206 Reverse Linked List', '#92 Reverse Linked List II'])
  })

  it('waits for typing to pause before searching', async () => {
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
      for (const text of ['t', 'tw', 'two']) {
        setter.call(input(), text)
        input().dispatchEvent(new Event('input', { bubbles: true }))
      }
    })
    await settle()
    expect(searches).toEqual(['two'])
  })
})

describe('picking', () => {
  it('turns the highlighted match into a bubble with Enter, a comma, or Tab', async () => {
    await type('two sum')
    await press('Enter')
    await type('3s')
    await press(',')
    await type('206')
    await press('Tab')
    expect(bubbles()).toEqual(['#1 Two Sum', '#15 3sum', '#206 Reverse Linked List'])
    expect(latest.map((p) => p.difficulty)).toEqual(['Easy', 'Medium', 'Easy'])
    expect(input().value).toBe('')
  })

  it('moves through the matches with the arrow keys', async () => {
    await type('two')
    await press('ArrowDown')
    await press('Enter')
    expect(bubbles()).toEqual(['#167 Two Sum II Input Array Is Sorted'])
  })

  it('picks a match on click', async () => {
    await type('reverse')
    await act(async () => {
      container.querySelectorAll('.picker-match')[1].dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }))
    })
    expect(bubbles()).toEqual(['#92 Reverse Linked List II'])
  })

  it("won't pick a problem twice", async () => {
    await type('1')
    await press('Enter')
    await type('two sum')
    await press('Enter')
    expect(bubbles()).toEqual(['#1 Two Sum'])
    expect(message()).toBe('#1 is already picked.')
  })

  it('removes a bubble with its button, or the last one with Backspace in an empty box', async () => {
    await paste('1, 15, 206')
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="Remove #15 3sum"]')!.click())
    expect(bubbles()).toEqual(['#1 Two Sum', '#206 Reverse Linked List'])
    await press('Backspace')
    expect(bubbles()).toEqual(['#1 Two Sum'])
  })
})

describe('numbers', () => {
  it('picks only the exact problem for a number, not the first that starts with it', async () => {
    await type('146')
    expect(matches()).toEqual(['#1460 Make Two Arrays Equal By Reversing Subarrays'])
    await press('Enter')
    expect(bubbles()).toEqual([])
    expect(message()).toContain("#146 isn't in the imported problems")
  })

  it('makes a problem not in the dataset a LeetCode-only bubble when its title is given', async () => {
    await type('146 LRU Cache')
    await press('Enter')
    expect(bubbles()).toEqual(['#146 LRU Cache'])
    expect(container.querySelector('.pick')!.textContent).toContain('Solved on LeetCode')
    expect(latest).toEqual([{ number: 146, title: 'LRU Cache', difficulty: null }])
  })

  it("refuses a title that names a different problem than the dataset's for that number", async () => {
    await type('1 Add Two Numbers')
    await press('Enter')
    expect(bubbles()).toEqual([])
    expect(message()).toBe('#1 is Two Sum, not Add Two Numbers.')
  })

  it('says when nothing matches', async () => {
    await type('zebra')
    await press('Enter')
    expect(message()).toBe('No imported problem matches "zebra".')
  })
})

describe('pasting', () => {
  it('splits at commas and line breaks and picks numbers and exact titles, leaving the rest to search', async () => {
    await paste('1, Reverse Linked List\n146. LRU Cache, linked')
    expect(bubbles()).toEqual(['#1 Two Sum', '#206 Reverse Linked List', '#146 LRU Cache'])
    expect(input().value).toBe('linked')
  })

  it('says why pieces were refused', async () => {
    await paste('146, 1, 1')
    expect(bubbles()).toEqual(['#1 Two Sum'])
    expect(message()).toContain("#146 isn't in the imported problems")
    expect(message()).toContain('#1 is already picked.')
  })

  it('says a number is already picked before saying it is not in the dataset', async () => {
    await paste('146. LRU Cache, 146')
    expect(bubbles()).toEqual(['#146 LRU Cache'])
    expect(message()).toBe('#146 is already picked.')
  })

  it('pastes text without commas or line breaks as typing', async () => {
    await paste('two sum')
    expect(bubbles()).toEqual([])
  })
})

describe('with nothing imported', () => {
  beforeEach(async () => {
    await act(async () => root.render(<Harness nothingImported />))
  })

  it('says nothing is imported instead of that nothing matches', async () => {
    await type('koko')
    await press('Enter')
    expect(container.querySelector('.problem-picker .muted')!.textContent).toContain('No LeetCode problems are imported')
    expect(message()).toBeNull()
  })

  it('still takes a number and title, to be solved on LeetCode', async () => {
    await type('875 Koko Eating Bananas')
    await press('Enter')
    expect(bubbles()).toEqual(['#875 Koko Eating Bananas'])
    expect(latest[0].difficulty).toBeNull()
  })
})

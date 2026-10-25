import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import type { KedamiApi } from '../../../preload/api'
import { NewLessonScreen } from './NewLessonScreen'

let container: HTMLDivElement
let root: Root
let fetchMock: Mock
let created: string[]

beforeEach(async () => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  created = []
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  fetchMock = vi.fn(async (url: string) => {
    const path = new URL(url).pathname
    if (path === '/leetcode/search') {
      const problems = [{ number: 1, slug: 'two-sum', title: 'Two Sum', difficulty: 'Easy' }]
      return new Response(JSON.stringify({ problems, imported: true }))
    }
    if (path === '/lessons') return new Response(JSON.stringify({ id: 'new-lesson' }), { status: 201 })
    throw new Error(`unexpected ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  await act(async () =>
    root.render(<NewLessonScreen folderId={null} onCreated={(id) => created.push(id)} onBack={() => {}} />)
  )
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const radio = (label: string) =>
  [...container.querySelectorAll('label.option')].find((l) => l.textContent === label)!.querySelector('input')!
const generate = () => container.querySelector<HTMLButtonElement>('button[type="submit"]')!
const settle = () => act(async () => new Promise((resolve) => setTimeout(resolve, 200)))

async function pick(text: string) {
  const input = container.querySelector<HTMLInputElement>('.picker-input')!
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, text)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await settle()
  await act(async () => input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })))
  await settle()
}

describe('a new computer science lesson', () => {
  it('asks for the domain, with DSA chosen, and swaps the problem set file for the picker', async () => {
    expect(container.querySelector('.problem-picker')).toBeNull()
    await act(async () => radio('Computer Science').click())
    expect(radio('Data structures and algorithms').checked).toBe(true)
    expect(container.querySelector('.problem-picker')).not.toBeNull()
    expect(container.querySelector('.file-drop')!.textContent).toContain('Drop reference')
    expect(generate().disabled).toBe(true)
  })

  it('sends the picked problems as the problem set, with the domain, and other files as reference', async () => {
    await act(async () => radio('Computer Science').click())
    await pick('two sum')
    const notes = new File(['Hash maps'], 'notes.md', { type: 'text/markdown' })
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!
    Object.defineProperty(input, 'files', { value: [notes], configurable: true })
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })))
    expect(container.querySelector('.file-row select')).toBeNull()

    expect(generate().disabled).toBe(false)
    await act(async () => generate().click())
    await settle()
    expect(created).toEqual(['new-lesson'])

    const [, init] = fetchMock.mock.calls.find(([url]) => new URL(url).pathname === '/lessons')!
    const form = init.body as FormData
    expect(form.get('subject')).toBe('computer_science')
    expect(form.get('domain')).toBe('dsa')
    expect(form.getAll('roles')).toEqual(['problem_set', 'reference'])
    const [problems, reference] = form.getAll('files') as File[]
    expect(problems.name).toBe('problems.md')
    expect(await problems.text()).toBe('1. Two Sum\n')
    expect(reference.name).toBe('notes.md')
  })

  it('sends no domain for other subjects and keeps the problem set file', async () => {
    await act(async () => radio('Computer Science').click())
    await act(async () => radio('Math').click())
    expect(container.querySelector('.problem-picker')).toBeNull()
    expect(container.querySelector('.file-drop')!.textContent).toContain('Drop PDFs')
  })
})

describe('a new SQL lesson', () => {
  const chapters = [
    { number: 1, name: 'Selecting', source: 'spider', available: 0 },
    { number: 2, name: 'Filtering', source: 'spider', available: 12 },
    { number: 10, name: 'Outer and self joins', source: 'pgexercises', available: 2 }
  ]
  const spider = (n: number) => ({ source: 'spider', id: `music-${n}`, text: `Question ${n}?`, database: 'music' })
  const page = { source: 'pgexercises', id: 'joins/self.html', text: 'Members who recommended', database: null }
  let recommendBodies: { chapter: number; count: number; round: number }[]

  beforeEach(() => {
    recommendBodies = []
    const base = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = new URL(url).pathname
      if (path === '/sql/chapters') return new Response(JSON.stringify({ chapters, imported: false }))
      if (path === '/sql/recommend') {
        const body = JSON.parse(init!.body as string)
        recommendBodies.push(body)
        if (body.chapter === 10) return new Response(JSON.stringify({ problems: [page], available: 2 }))
        const first = body.round * 2 + 1
        return new Response(JSON.stringify({ problems: [spider(first), spider(first + 1)], available: 12 }))
      }
      if (path === '/sql/database') {
        const file = (init!.body as FormData).get('file') as File
        if (file.name === 'bad.sql') return new Response(JSON.stringify({ detail: 'bad.sql failed: syntax error' }), { status: 422 })
        return new Response(JSON.stringify({ name: 'school', tables: [{ name: 'student', count: 3 }, { name: 'enrolled', count: 1 }] }))
      }
      return base(url, init)
    })
  })

  async function chooseSql() {
    await act(async () => radio('Computer Science').click())
    await act(async () => radio('SQL').click())
    await settle()
  }

  const button = (label: string) => [...container.querySelectorAll('button')].find((b) => b.textContent === label)
  const select = () => container.querySelector<HTMLSelectElement>('.chapter-picker select')!
  const rows = () => [...container.querySelectorAll('.recommended-row')].map((r) => r.textContent)

  async function chooseChapter(number: number) {
    await act(async () => {
      select().value = String(number)
      select().dispatchEvent(new Event('change', { bubbles: true }))
    })
  }

  async function click(label: string) {
    await act(async () => button(label)!.click())
    await settle()
  }

  async function addFiles(...files: File[]) {
    const input = container.querySelector<HTMLInputElement>('.file-drop input[type="file"]')!
    Object.defineProperty(input, 'files', { value: files, configurable: true })
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })))
    await settle()
  }

  const text = (name: string) => new File(['x'], name, { type: 'text/plain' })
  const sentForm = () => fetchMock.mock.calls.find(([url]) => new URL(url).pathname === '/lessons')![1].body as FormData

  describe('learning a chapter', () => {
    it('is the default, with the chapters and their counts and no file drop', async () => {
      await chooseSql()
      expect(radio('Learn a chapter').checked).toBe(true)
      expect(container.querySelector('.file-drop')).toBeNull()
      expect([...select().options].map((o) => o.textContent)).toEqual([
        '1. Selecting (0 problems)',
        '2. Filtering (12 problems)',
        '10. Outer and self joins (2 problems)'
      ])
      expect(container.textContent).toContain('examples use its people database')
      expect(generate().disabled).toBe(true)
    })

    it('says when a Spider chapter has nothing because nothing is imported', async () => {
      await chooseSql()
      expect(container.textContent).toContain('none are imported')
      expect(button('Recommend problems')!.disabled).toBe(true)
    })

    it('recommends, recommends again with the next round, and removes a problem', async () => {
      await chooseSql()
      await chooseChapter(2)
      await click('Recommend problems')
      expect(recommendBodies).toEqual([{ chapter: 2, count: 5, round: 0 }])
      expect(rows()).toEqual(['Question 1?musicRemove', 'Question 2?musicRemove'])
      await click('Recommend again')
      expect(recommendBodies[1]).toEqual({ chapter: 2, count: 5, round: 1 })
      expect(rows()).toEqual(['Question 3?musicRemove', 'Question 4?musicRemove'])
      await act(async () => container.querySelector<HTMLButtonElement>('.recommended-row button')!.click())
      expect(rows()).toEqual(['Question 4?musicRemove'])
    })

    it('says when a chapter has fewer problems than asked, and marks pgexercises problems', async () => {
      await chooseSql()
      await chooseChapter(10)
      await click('Recommend problems')
      expect(rows()).toEqual(['Members who recommendedSolved on pgexercisesRemove'])
      expect(container.textContent).toContain('This chapter has 2 problems.')
    })

    it('starts over when the chapter changes', async () => {
      await chooseSql()
      await chooseChapter(2)
      await click('Recommend problems')
      await chooseChapter(10)
      expect(rows()).toEqual([])
      expect(button('Recommend problems')).toBeDefined()
      expect(generate().disabled).toBe(true)
    })

    it('sends only the recommended problems, with the chapter', async () => {
      await chooseSql()
      await chooseChapter(2)
      await click('Recommend problems')
      await act(async () => generate().click())
      await settle()
      expect(created).toEqual(['new-lesson'])
      const form = sentForm()
      expect(form.get('domain')).toBe('sql')
      expect(form.get('chapter')).toBe('2')
      expect(form.getAll('roles')).toEqual(['problem_set'])
      const [problems] = form.getAll('files') as File[]
      expect(problems.name).toBe('problems.md')
      expect(await problems.text()).toBe('1. spider:music-1 Question 1?\n2. spider:music-2 Question 2?\n')
    })
  })

  describe('uploading a problem set', () => {
    async function chooseUpload() {
      await chooseSql()
      await act(async () => radio('Upload a problem set').click())
    }

    async function pickDatabase(file: File) {
      const input = container.querySelector<HTMLInputElement>('input[aria-label="Course database"]')!
      Object.defineProperty(input, 'files', { value: [file], configurable: true })
      await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })))
      await settle()
    }

    it('checks the database as soon as it is picked and sends it with the problem set', async () => {
      await chooseUpload()
      await addFiles(text('ps2.md'))
      await pickDatabase(text('school.sql'))
      const slot = container.querySelector('.database-slot')!
      expect(slot.textContent).toContain('school.sql')
      expect(slot.textContent).toContain('student (3 rows), enrolled (1 row)')
      await act(async () => generate().click())
      await settle()
      const form = sentForm()
      expect(form.get('chapter')).toBeNull()
      expect(form.getAll('roles')).toEqual(['problem_set', 'database'])
      expect((form.getAll('files') as File[]).map((f) => f.name)).toEqual(['ps2.md', 'school.sql'])
    })

    it('shows why a database was refused and waits for it to be removed or replaced', async () => {
      await chooseUpload()
      await addFiles(text('ps2.md'))
      await pickDatabase(text('bad.sql'))
      expect(container.querySelector('.database-slot')!.textContent).toContain('bad.sql failed: syntax error')
      expect(generate().disabled).toBe(true)
      await act(async () => container.querySelector<HTMLButtonElement>('.database-slot button')!.click())
      expect(container.querySelector('.database-slot')!.textContent).not.toContain('bad.sql')
      expect(generate().disabled).toBe(false)
    })

    it('moves a database dropped among the material to the slot', async () => {
      await chooseUpload()
      await addFiles(text('ps2.md'), text('school.sql'))
      expect([...container.querySelectorAll('.file-list .file-row')].map((r) => r.querySelector('.file-name')!.textContent)).toEqual(['ps2.md'])
      expect(container.querySelector('.database-slot')!.textContent).toContain('school.sql')
    })

    it('works without a database', async () => {
      await chooseUpload()
      await addFiles(text('ps2.md'))
      expect(container.querySelector('.database-slot')!.textContent).toContain('Without it, they are self checks')
      await act(async () => generate().click())
      await settle()
      expect(sentForm().getAll('roles')).toEqual(['problem_set'])
    })
  })

  it('refuses a database file outside a SQL lesson', async () => {
    await act(async () => radio('Math').click())
    await addFiles(text('ps.md'), text('school.sql'))
    expect(container.textContent).toContain('Not supported, so not added: school.sql')
  })
})

describe('choosing who builds the lesson', () => {
  // Renders the screen again once the server says whether it has an API key.
  async function open(api: boolean) {
    const base = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) =>
      new URL(url).pathname === '/capabilities' ? new Response(JSON.stringify({ api })) : base(url, init)
    )
    await act(async () =>
      root.render(
        <NewLessonScreen key={String(api)} folderId={null} onCreated={(id) => created.push(id)} onBack={() => {}} />
      )
    )
    await settle()
  }

  async function addProblemSet() {
    const input = container.querySelector<HTMLInputElement>('.file-drop input[type="file"]')!
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'ps1.md', { type: 'text/plain' })], configurable: true })
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })))
  }

  async function send() {
    await act(async () => generate().click())
    await settle()
    return fetchMock.mock.calls.find(([url]) => new URL(url).pathname === '/lessons')![1].body as FormData
  }

  it('offers the API by default when there is a key, and sends no builder for it', async () => {
    await open(true)
    await act(async () => radio('Math').click())
    expect(radio('API').checked).toBe(true)
    expect(radio('Claude Code').checked).toBe(false)
    await addProblemSet()
    expect((await send()).get('builder')).toBeNull()
  })

  it('sends Claude Code as the builder when it is chosen, and says what to run', async () => {
    await open(true)
    await act(async () => radio('Physics').click())
    await act(async () => radio('Claude Code').click())
    expect(container.querySelector('code')?.textContent).toBe('/kedami:lesson')
    await addProblemSet()
    expect((await send()).get('builder')).toBe('agent')
  })

  it('has only Claude Code without a key', async () => {
    await open(false)
    await act(async () => radio('General').click())
    expect(radio('API').disabled).toBe(true)
    expect(radio('Claude Code').checked).toBe(true)
    await addProblemSet()
    expect((await send()).get('builder')).toBe('agent')
  })

  it('offers no choice for computer science, which needs a key', async () => {
    await open(true)
    await act(async () => radio('Computer Science').click())
    expect(container.querySelector('input[name="builder"]')).toBeNull()

    await open(false)
    await act(async () => radio('Computer Science').click())
    expect(container.textContent).toContain('Computer science lessons need an API key')
    expect(generate().disabled).toBe(true)
  })
})

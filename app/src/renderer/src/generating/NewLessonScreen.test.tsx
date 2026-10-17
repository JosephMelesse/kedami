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
  async function chooseSql() {
    await act(async () => radio('Computer Science').click())
    await act(async () => radio('SQL').click())
  }

  async function addFiles(...files: File[]) {
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!
    Object.defineProperty(input, 'files', { value: files, configurable: true })
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })))
  }

  const text = (name: string) => new File(['x'], name, { type: 'text/plain' })

  it('takes a problem set and the course database, sent with the SQL domain', async () => {
    await chooseSql()
    expect(container.querySelector('.problem-picker')).toBeNull()
    expect(container.querySelector('input[type="file"]')!.getAttribute('accept')).toContain('.sqlite')
    await addFiles(text('ps2.md'), text('school.sql'))
    const rows = [...container.querySelectorAll('.file-row')].map((r) => r.textContent)
    expect(rows[1]).toContain('Database')
    await act(async () => generate().click())
    await settle()
    const [, init] = fetchMock.mock.calls.find(([url]) => new URL(url).pathname === '/lessons')!
    const form = init.body as FormData
    expect(form.get('domain')).toBe('sql')
    expect(form.getAll('roles')).toEqual(['problem_set', 'database'])
  })

  it('takes one database at most', async () => {
    await chooseSql()
    await addFiles(text('ps2.md'), text('a.sqlite'), text('b.db'))
    expect(container.textContent).toContain('A SQL lesson takes one database.')
    expect(generate().disabled).toBe(true)
  })

  it('refuses a database file outside a SQL lesson', async () => {
    await act(async () => radio('Math').click())
    await addFiles(text('ps.md'), text('school.sql'))
    expect(container.textContent).toContain('Not supported, so not added: school.sql')
  })
})

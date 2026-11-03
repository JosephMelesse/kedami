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
  fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 'new-lesson' }), { status: 201 }))
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

async function addFiles(...names: string[]) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]')!
  const files = names.map((name) => new File(['text'], name))
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })))
}

describe('a new lesson', () => {
  it('offers math, physics, and general', () => {
    const labels = [...container.querySelectorAll('.subject-options label.option')].map((l) => l.textContent)
    expect(labels).toEqual(['Math', 'Physics', 'General'])
  })

  it('needs a subject and a problem set', async () => {
    expect(generate().disabled).toBe(true)
    await act(async () => radio('Physics').click())
    expect(generate().disabled).toBe(true)
    await addFiles('ps3.pdf')
    expect(generate().disabled).toBe(false)
  })

  it('takes the first file as the problem set and later ones as reference', async () => {
    await addFiles('ps3.pdf', 'notes.pdf')
    const roles = [...container.querySelectorAll<HTMLSelectElement>('.file-row select')].map((s) => s.value)
    expect(roles).toEqual(['problem_set', 'reference'])
  })

  it('says when no file is tagged as a problem set', async () => {
    await act(async () => radio('Physics').click())
    await addFiles('ps3.pdf')
    const select = container.querySelector<HTMLSelectElement>('.file-row select')!
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')!.set!
      setter.call(select, 'reference')
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })
    expect(container.textContent).toContain('Tag at least one file as a problem set.')
    expect(generate().disabled).toBe(true)
  })

  it('refuses a file it cannot read, such as a database', async () => {
    await addFiles('ps3.pdf', 'tables.sqlite')
    expect(container.textContent).toContain('Not supported, so not added: tables.sqlite')
    expect(container.querySelectorAll('.file-row')).toHaveLength(1)
  })

  it('sends the subject and each file with its role', async () => {
    await act(async () => radio('Physics').click())
    await addFiles('ps3.pdf', 'notes.pdf')
    await act(async () => generate().click())

    const [url, init] = fetchMock.mock.calls[0]
    expect(new URL(url).pathname).toBe('/lessons')
    const form = init.body as FormData
    expect(form.get('subject')).toBe('physics')
    expect(form.getAll('roles')).toEqual(['problem_set', 'reference'])
    expect(form.has('domain')).toBe(false)
    expect(form.has('chapter')).toBe(false)
    expect(created).toEqual(['new-lesson'])
  })
})

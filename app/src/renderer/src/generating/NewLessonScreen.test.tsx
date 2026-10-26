import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import type { KedamiApi } from '../../../preload/api'
import { NewLessonScreen } from './NewLessonScreen'

let container: HTMLDivElement
let root: Root
let fetchMock: Mock
let created: string[]
let claudeInstalled: boolean

beforeEach(async () => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  created = []
  claudeInstalled = true
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  fetchMock = vi.fn(async (url: string) => {
    const path = new URL(url).pathname
    if (path === '/lessons') return new Response(JSON.stringify({ id: 'new-lesson' }), { status: 201 })
    if (path === '/jobs') return new Response(JSON.stringify({ claude: claudeInstalled, running: null, queued: [] }))
    throw new Error(`unexpected ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  await act(async () =>
    root.render(<NewLessonScreen folderId={7} onCreated={(id) => created.push(id)} onBack={() => {}} />)
  )
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const radio = (label: string) =>
  [...container.querySelectorAll('label.option')].find((l) => l.textContent === label)?.querySelector('input')
const create = () => container.querySelector<HTMLButtonElement>('button[type="submit"]')!
const text = (name: string) => new File(['x'], name, { type: 'text/plain' })

async function addFiles(...files: File[]) {
  const input = container.querySelector<HTMLInputElement>('.file-drop input[type="file"]')!
  Object.defineProperty(input, 'files', { value: files, configurable: true })
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })))
}

describe('a new lesson', () => {
  it('offers math, physics, and general, and no computer science', () => {
    expect(radio('Math')).toBeDefined()
    expect(radio('Physics')).toBeDefined()
    expect(radio('General')).toBeDefined()
    expect(radio('Computer Science')).toBeUndefined()
  })

  it('says Claude Code builds it once created, with nothing to type', () => {
    expect(container.querySelector('header')?.textContent).toContain('as soon as you create it')
    expect(container.querySelector('header code')).toBeNull()
  })

  it('without Claude Code installed, says to install it and keeps Create lesson disabled', async () => {
    claudeInstalled = false
    await act(async () => root.unmount())
    root = createRoot(container)
    await act(async () =>
      root.render(<NewLessonScreen folderId={7} onCreated={(id) => created.push(id)} onBack={() => {}} />)
    )
    await act(async () => radio('Math')!.click())
    await addFiles(text('pset.md'))
    expect(create().disabled).toBe(true)
    expect(container.textContent).toContain("Claude Code isn't installed")
  })

  it('needs a subject and a problem set', async () => {
    expect(create().disabled).toBe(true)
    await act(async () => radio('Math')!.click())
    expect(create().disabled).toBe(true)
    await addFiles(text('pset.md'))
    expect(create().disabled).toBe(false)
  })

  it('takes the first file as the problem set and the rest as reference, and rejects unsupported files', async () => {
    await addFiles(text('pset.md'), text('ref.md'), text('slides.pptx'))
    const roles = [...container.querySelectorAll<HTMLSelectElement>('.file-row select')].map((s) => s.value)
    expect(roles).toEqual(['problem_set', 'reference'])
    expect(container.querySelector('.answer-error')?.textContent).toBe('Not supported, so not added: slides.pptx')
  })

  it('sends the subject, folder, files, and roles, and nothing else', async () => {
    await act(async () => radio('Physics')!.click())
    await addFiles(text('pset.md'), text('ref.md'))
    await act(async () => create().click())
    expect(created).toEqual(['new-lesson'])

    const [, init] = fetchMock.mock.calls.find(([url]) => new URL(url).pathname === '/lessons')!
    const form = init.body as FormData
    expect([...new Set(form.keys())]).toEqual(['subject', 'folder', 'files', 'roles'])
    expect([form.get('subject'), form.get('folder')]).toEqual(['physics', '7'])
    expect((form.getAll('files') as File[]).map((f) => f.name)).toEqual(['pset.md', 'ref.md'])
    expect(form.getAll('roles')).toEqual(['problem_set', 'reference'])
  })

  it('asks for a problem set when every file is reference', async () => {
    await act(async () => radio('Math')!.click())
    await addFiles(text('pset.md'))
    const select = container.querySelector<HTMLSelectElement>('.file-row select')!
    await act(async () => {
      select.value = 'reference'
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })
    expect(container.textContent).toContain('Tag at least one file as a problem set.')
    expect(create().disabled).toBe(true)
  })
})

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { saveFolderNote } from '../api'
import { deleteSummary } from './folders'
import { FolderNote } from './FolderNote'

vi.mock('../api', async (original) => ({
  ...(await original<typeof import('../api')>()),
  saveFolderNote: vi.fn(async () => undefined)
}))

const save = vi.mocked(saveFolderNote)
let container: HTMLDivElement
let root: Root

const box = () => container.querySelector('textarea')!

async function type(value: string) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!
    setter.call(box(), value)
    box().dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function show(folderId: number, initial: string, onChange: (note: string) => void = () => {}) {
  await act(async () => root.render(<FolderNote key={folderId} folderId={folderId} initial={initial} onChange={onChange} />))
}

beforeEach(() => {
  vi.useFakeTimers()
  save.mockReset()
  save.mockResolvedValue(undefined)
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.useRealTimers()
})

describe('FolderNote', () => {
  it('saves a second after typing stops, once', async () => {
    await show(1, '')
    await type('a')
    await act(async () => vi.advanceTimersByTime(500))
    await type('ab')
    await act(async () => vi.advanceTimersByTime(999))
    expect(save).not.toHaveBeenCalled()
    await act(async () => vi.advanceTimersByTime(1))
    expect(save.mock.calls).toEqual([[1, 'ab']])
  })

  it('saves nothing when nothing changed', async () => {
    await show(1, 'Saved')
    await act(async () => vi.advanceTimersByTime(5000))
    expect(save).not.toHaveBeenCalled()
  })

  it('keeps what is typed when a background refresh brings an older note', async () => {
    await show(1, 'Old')
    await type('New')
    await show(1, 'Old')
    expect(box().value).toBe('New')
  })

  it('saves to the folder it was typed in when the student leaves for another', async () => {
    await show(1, '')
    await type('For folder 1')
    await show(2, 'Folder 2')
    expect(save.mock.calls).toEqual([[1, 'For folder 1']])
    expect(box().value).toBe('Folder 2')
  })

  it('reports each change', async () => {
    const seen: string[] = []
    await show(1, '', (note) => seen.push(note))
    await type('x')
    expect(seen).toEqual(['x'])
  })

  it('shows a message and keeps the text when a save fails, and clears it when one works', async () => {
    save.mockRejectedValueOnce(new Error('no server'))
    await show(1, '')
    await type('Important')
    await act(async () => vi.advanceTimersByTime(1000))
    expect(container.textContent).toContain('Could not save this note')
    expect(box().value).toBe('Important')
    await type('Important!')
    await act(async () => vi.advanceTimersByTime(1000))
    expect(container.textContent).not.toContain('Could not save this note')
  })
})

describe('the delete confirmation', () => {
  const folder = (note: string) => ({ id: 1, name: 'A', parent_id: null, lessons: 0, own_lessons: 0, subfolders: 0, note })

  it('says the note is deleted only when it is not empty', () => {
    expect(deleteSummary(folder(''), 'Lessons')).toBe('The folder is empty.')
    expect(deleteSummary(folder(' \n  '), 'Lessons')).toBe('The folder is empty.')
    expect(deleteSummary(folder('Plan'), 'Lessons')).toBe('The folder is empty. Its note is deleted.')
    expect(deleteSummary({ ...folder('Plan'), own_lessons: 2 }, 'Physics')).toBe(
      'Its 2 lessons move up to Physics. Its note is deleted.'
    )
  })
})

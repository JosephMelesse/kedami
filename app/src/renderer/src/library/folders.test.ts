import { describe, expect, it } from 'vitest'
import type { Folder } from '../api'
import { deleteSummary, folderPath, foldersAbove, moveTargets } from './folders'

function folder(id: number, name: string, parent_id: number | null = null): Folder {
  return { id, name, parent_id, lessons: 0, own_lessons: 0, subfolders: 0 }
}

// As the server lists them: by name.
const FOLDERS = [
  folder(2, 'Calculus'),
  folder(1, 'Physics'),
  folder(5, 'Part A', 3),
  folder(3, 'Week 1', 1),
  folder(4, 'Week 1', 2)
]

describe('foldersAbove and folderPath', () => {
  it('walks from the top level down', () => {
    const part = FOLDERS[2]
    expect(foldersAbove(FOLDERS, part).map((f) => f.id)).toEqual([1, 3])
    expect(folderPath(FOLDERS, part)).toBe('Physics / Week 1 / Part A')
  })

  it('tells apart two folders with the same name', () => {
    expect(folderPath(FOLDERS, FOLDERS[3])).toBe('Physics / Week 1')
    expect(folderPath(FOLDERS, FOLDERS[4])).toBe('Calculus / Week 1')
  })

  it('has nothing above a top-level folder', () => {
    expect(foldersAbove(FOLDERS, FOLDERS[0])).toEqual([])
  })
})

describe('moveTargets', () => {
  const labels = (targets: ReturnType<typeof moveTargets>) => targets.map((t) => `${t.label}${t.disabled ? ' (x)' : ''}`)

  it('lists home, then each folder above what is inside it', () => {
    expect(labels(moveTargets(FOLDERS, 2))).toEqual([
      'Lessons',
      'Calculus (x)',
      'Calculus / Week 1',
      'Physics',
      'Physics / Week 1',
      'Physics / Week 1 / Part A'
    ])
  })

  it('disables home for something already there', () => {
    expect(moveTargets(FOLDERS, null)[0]).toEqual({ id: null, label: 'Lessons', disabled: true })
  })

  it('disables a moving folder, everything inside it, and where it already is', () => {
    expect(labels(moveTargets(FOLDERS, 1, 3))).toEqual([
      'Lessons',
      'Calculus',
      'Calculus / Week 1',
      'Physics (x)',
      'Physics / Week 1 (x)',
      'Physics / Week 1 / Part A (x)'
    ])
  })
})

describe('deleteSummary', () => {
  const contents = (own_lessons: number, subfolders: number) => ({ ...folder(1, 'A'), own_lessons, subfolders })

  it('names what moves and where', () => {
    expect(deleteSummary(contents(0, 0), 'Lessons')).toBe('The folder is empty.')
    expect(deleteSummary(contents(1, 0), 'Lessons')).toBe('Its 1 lesson moves up to Lessons.')
    expect(deleteSummary(contents(0, 1), 'Physics')).toBe('Its 1 subfolder moves up to Physics.')
    expect(deleteSummary(contents(3, 2), 'Physics')).toBe('Its 3 lessons and 2 subfolders move up to Physics.')
    expect(deleteSummary(contents(1, 1), 'Physics')).toBe('Its 1 lesson and 1 subfolder move up to Physics.')
  })
})

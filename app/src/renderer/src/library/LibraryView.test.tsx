import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Folder, LessonSummary } from '../api'
import { LessonMenu } from './LessonMenu'
import { LibraryView } from './LibraryScreen'

function summary(overrides: Partial<LessonSummary>): LessonSummary {
  return {
    id: 'sample',
    title: 'Projectile motion',
    subject: 'physics',
    status: 'ready',
    current_stage: null,
    error: null,
    folder_id: null,
    created: '2026-10-03T00:00:00+00:00',
    problems_total: 2,
    problems_done: 1,
    ...overrides
  }
}

const WEEK3: Folder = { id: 3, name: 'Week 3', lessons: 1 }
const noop = () => {}

function render(lessons: LessonSummary[], folders: Folder[] = [], folder: Folder | null = null): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(
    <LibraryView
      lessons={lessons}
      folders={folders}
      folder={folder}
      problem={null}
      onOpen={noop}
      onNew={noop}
      onOpenFolder={noop}
      onHome={noop}
      onNewFolder={noop}
      onRenameFolder={noop}
      onDeleteFolder={noop}
      onRename={noop}
      onMove={noop}
      onDelete={noop}
    />
  )
  return root
}

const titles = (root: HTMLElement) => [...root.querySelectorAll('.tile-title')].map((e) => e.textContent)

describe('LibraryView', () => {
  it('shows folders first, then lessons on the home page, then the new lesson tile', () => {
    const lessons = [
      summary({ id: 'a', title: 'First' }),
      summary({ id: 'b', title: 'Filed', folder_id: 3 }),
      summary({ id: 'c', title: 'Second' })
    ]
    const root = render(lessons, [WEEK3])
    expect(titles(root)).toEqual(['Week 3', 'First', 'Second', 'New lesson'])
    expect(root.querySelector('h1')?.textContent).toBe('Lessons')
    expect(root.textContent).toContain('New folder')
    expect(root.textContent).toContain('1 lesson')
  })

  it('shows only a folder’s lessons inside it, with a way home and to delete the folder', () => {
    const lessons = [summary({ id: 'a', title: 'Home' }), summary({ id: 'b', title: 'Filed', folder_id: 3 })]
    const root = render(lessons, [WEEK3], WEEK3)
    expect(titles(root)).toEqual(['Filed', 'New lesson'])
    expect(root.querySelector('h1')?.textContent).toBe('Week 3')
    expect(root.querySelector('.library-nav')?.textContent).toBe('Lessons')
    expect(root.textContent).toContain('Delete folder')
    expect(root.textContent).toContain('Rename')
    expect(root.textContent).not.toContain('New folder')
  })

  it('shows only the new lesson tile when there is nothing else', () => {
    const tiles = render([]).querySelectorAll<HTMLButtonElement>('.tile')
    expect(tiles).toHaveLength(1)
    expect(tiles[0].textContent).toBe('New lesson')
  })

  it('shows problem progress on ready lessons', () => {
    const root = render([summary({})])
    expect(root.textContent).toContain('1 of 2 problems done')
    expect(root.querySelector('.progress-fill')?.getAttribute('style')).toContain('width:50%')
  })

  it('shows status instead of progress while not ready', () => {
    const root = render([summary({ status: 'generating' }), summary({ id: 'f', status: 'failed' })])
    const [generating, failed] = root.querySelectorAll<HTMLButtonElement>('.tile')
    expect(generating.textContent).toContain('Generating')
    expect(failed.textContent).toContain('Generation failed')
    expect(root.querySelector('.progress-bar')).toBeNull()
  })

  it('gives every lesson an options button', () => {
    const root = render([summary({ id: 'a', title: 'First' })])
    expect(root.querySelector('.tile-menu-button')?.getAttribute('aria-label')).toBe('Options for First')
  })
})

describe('LessonMenu', () => {
  // The menu opens on click; render it open by clicking in a live DOM.
  async function openMenu(lesson: LessonSummary, folders: Folder[]): Promise<string[]> {
    const { createRoot } = await import('react-dom/client')
    const { act } = await import('react')
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    await act(async () => root.render(<LessonMenu lesson={lesson} folders={folders} onRename={noop} onMove={noop} onDelete={noop} />))
    await act(async () => container.querySelector<HTMLButtonElement>('.tile-menu-button')!.click())
    const items = [...container.querySelectorAll<HTMLButtonElement>('[role=menuitem]')].map(
      (item) => `${item.textContent}${item.disabled ? ' (disabled)' : ''}`
    )
    await act(async () => root.unmount())
    container.remove()
    return items
  }

  const folders = [WEEK3, { id: 4, name: 'Week 4', lessons: 0 }]

  it('offers rename, the other folders, and delete for a lesson on the home page', async () => {
    expect(await openMenu(summary({}), folders)).toEqual(['Rename', 'Move to Week 3', 'Move to Week 4', 'Delete lesson'])
  })

  it('offers rename, home, and the other folders for a lesson in a folder', async () => {
    expect(await openMenu(summary({ folder_id: 3 }), folders)).toEqual([
      'Rename',
      'Move to Lessons',
      'Move to Week 4',
      'Delete lesson'
    ])
  })

  it('offers rename but not delete while the lesson is generating', async () => {
    expect(await openMenu(summary({ status: 'generating' }), [])).toEqual(['Rename', 'Delete lesson (disabled)'])
  })

  it('closes the menu and asks for a new name on Rename', async () => {
    const { createRoot } = await import('react-dom/client')
    const { act } = await import('react')
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    let renamed = 0
    const onRename = () => renamed++
    await act(async () =>
      root.render(<LessonMenu lesson={summary({})} folders={[]} onRename={onRename} onMove={noop} onDelete={noop} />)
    )
    await act(async () => container.querySelector<HTMLButtonElement>('.tile-menu-button')!.click())
    await act(async () => container.querySelector<HTMLButtonElement>('[role=menuitem]')!.click())
    expect(renamed).toBe(1)
    expect(container.querySelector('[role=menu]')).toBeNull()
    await act(async () => root.unmount())
    container.remove()
  })
})

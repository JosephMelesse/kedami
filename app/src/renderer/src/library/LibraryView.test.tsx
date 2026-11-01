import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Folder, LessonSummary } from '../api'
import { formatDue } from './DueLabel'
import { LessonMenu } from './LessonMenu'
import { LibraryView } from './LibraryScreen'

function summary(overrides: Partial<LessonSummary>): LessonSummary {
  return {
    id: 'sample',
    title: 'Projectile motion',
    subject: 'physics',
    domain: null,
    status: 'ready',
    current_stage: null,
    error: null,
    folder_id: null,
    created: '2026-10-03T00:00:00+00:00',
    problems_total: 2,
    problems_done: 1,
    active: false,
    due_date: null,
    done: false,
    overdue: false,
    ...overrides
  }
}

function folderOf(overrides: Partial<Folder> & { id: number; name: string }): Folder {
  return { parent_id: null, lessons: 0, own_lessons: 0, subfolders: 0, note: '', next_due: null, next_due_overdue: false, ...overrides }
}

const WEEK3 = folderOf({ id: 3, name: 'Week 3', lessons: 1, own_lessons: 1 })
const noop = () => {}

function render(lessons: LessonSummary[], folders: Folder[] = [], folder: Folder | null = null): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(
    <LibraryView
      lessons={lessons}
      folders={folders}
      folder={folder}
      problem={null}
      notice={null}
      onOpen={noop}
      onNew={noop}
      onOpenFolder={noop}
      onHome={noop}
      onNewFolder={noop}
      onRenameFolder={noop}
      onMoveFolder={noop}
      onDeleteFolder={noop}
      onRename={noop}
      onMove={noop}
      onDueDate={noop}
      onSetActive={noop}
      onDelete={noop}
      onNoteChange={noop}
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
    expect(root.textContent).toContain('New folder')
    expect(root.textContent).toContain('Move')
  })

  it('shows a folder’s subfolders, then its lessons, then the new lesson tile, with a breadcrumb back up', () => {
    const physics = folderOf({ id: 1, name: 'Physics', lessons: 2, subfolders: 1 })
    const week = folderOf({ id: 2, name: 'Week 1', parent_id: 1, lessons: 2, own_lessons: 1, subfolders: 1 })
    const part = folderOf({ id: 4, name: 'Part A', parent_id: 2, lessons: 1, own_lessons: 1 })
    const lessons = [summary({ id: 'a', title: 'Filed', folder_id: 2 }), summary({ id: 'b', title: 'Deep', folder_id: 4 })]
    const root = render(lessons, [physics, week, part], week)
    expect(titles(root)).toEqual(['Part A', 'Filed', 'New lesson'])
    expect(root.querySelector('h1')?.textContent).toBe('Week 1')
    expect(root.querySelector('.library-nav')?.textContent).toBe('Lessons / Physics')
  })

  it('shows only top-level folders on the home page, counting the lessons in their subfolders', () => {
    const physics = folderOf({ id: 1, name: 'Physics', lessons: 2, subfolders: 1 })
    const week = folderOf({ id: 2, name: 'Week 1', parent_id: 1, lessons: 2, own_lessons: 2 })
    const root = render([], [physics, week])
    expect(titles(root)).toEqual(['Physics', 'New lesson'])
    expect(root.textContent).toContain('2 lessons')
  })

  it('shows the note at the top of a folder, and none on the home page', () => {
    const noted = folderOf({ id: 3, name: 'Week 3', note: 'Exam on Friday' })
    const inside = render([], [noted], noted)
    expect(inside.querySelector<HTMLTextAreaElement>('.folder-note textarea')?.textContent).toBe('Exam on Friday')
    expect(inside.querySelector('.library > :nth-child(3)')?.className).toBe('folder-note')
    expect(render([], [noted]).querySelector('.folder-note')).toBeNull()
  })

  it('shows a notice, such as a folder renamed by a delete', () => {
    const root = document.createElement('div')
    root.innerHTML = renderToString(
      <LibraryView
        lessons={[]}
        folders={[]}
        folder={null}
        problem={null}
        notice="Week 1 is now Week 1 (2), since that name was taken."
        onOpen={noop}
        onNew={noop}
        onOpenFolder={noop}
        onHome={noop}
        onNewFolder={noop}
        onRenameFolder={noop}
        onMoveFolder={noop}
        onDeleteFolder={noop}
        onRename={noop}
        onMove={noop}
        onDueDate={noop}
        onSetActive={noop}
        onDelete={noop}
        onNoteChange={noop}
      />
    )
    expect(root.textContent).toContain('Week 1 is now Week 1 (2)')
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

describe('Active lessons', () => {
  const active = (root: HTMLElement) => root.querySelector<HTMLElement>('.active-lessons')
  const rows = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>('.active-row')]
  const boxes = (row: HTMLElement) =>
    [...row.querySelectorAll('.problem-box')].map((box) => (box.classList.contains('problem-box-done') ? 'done' : 'left'))

  it('shows no card when no lesson is active', () => {
    expect(active(render([summary({})]))).toBeNull()
  })

  it('lists the active lessons from every folder in one card on the home page, before the folders', () => {
    const lessons = [
      summary({ id: 'a', title: 'First', active: true }),
      summary({ id: 'b', title: 'Filed', folder_id: 3, active: true }),
      summary({ id: 'c', title: 'Idle' })
    ]
    const root = render(lessons, [WEEK3])
    expect(active(root)?.querySelector('h2')?.textContent).toBe('Active')
    expect(rows(root).map((row) => row.querySelector('.active-title')?.textContent)).toEqual(['First', 'Filed'])
    expect(titles(root)).toEqual(['Week 3', 'First', 'Idle', 'New lesson'])
    expect(root.querySelector('.library > :nth-child(2)')?.className).toBe('active-lessons')
  })

  it('is not shown inside a folder', () => {
    const root = render([summary({ folder_id: 3, active: true })], [WEEK3], WEEK3)
    expect(active(root)).toBeNull()
  })

  it('fills a box for each done problem, from the left, and counts the rest', () => {
    const [row] = rows(render([summary({ active: true, problems_total: 4, problems_done: 1 })]))
    expect(boxes(row)).toEqual(['done', 'left', 'left', 'left'])
    expect(row.textContent).toContain('3 problems left')
    expect(row.querySelector('.problem-boxes')?.getAttribute('aria-label')).toBe('1 of 4 problems done')
  })

  it('says one problem left, and all problems done once none are', () => {
    const root = render([
      summary({ id: 'a', active: true, problems_total: 2, problems_done: 1 }),
      summary({ id: 'b', active: true, problems_total: 2, problems_done: 2 })
    ])
    const [one, all] = rows(root)
    expect(one.textContent).toContain('1 problem left')
    expect(boxes(all)).toEqual(['done', 'done'])
    expect(all.textContent).toContain('All problems done')
  })

  it('shows Generating instead of boxes while an active lesson reruns', () => {
    const [row] = rows(render([summary({ active: true, status: 'generating', problems_total: 0, problems_done: 0 })]))
    expect(row.textContent).toContain('Generating')
    expect(row.querySelector('.problem-boxes')).toBeNull()
  })

  it('gives only ready lessons an Active checkbox, checked when active', () => {
    const root = render([
      summary({ id: 'a', title: 'On', active: true }),
      summary({ id: 'b', title: 'Off' }),
      summary({ id: 'c', title: 'New', status: 'generating' }),
      summary({ id: 'd', title: 'Broken', status: 'failed' })
    ])
    const checkboxes = [...root.querySelectorAll<HTMLInputElement>('.tile-active input')]
    expect(checkboxes.map((box) => [box.getAttribute('aria-label'), box.checked])).toEqual([
      ['Active: On', true],
      ['Active: Off', false]
    ])
  })

  it('marks a lesson active without opening it, and opens it from its row', async () => {
    const { createRoot } = await import('react-dom/client')
    const { act } = await import('react')
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    const calls: string[] = []
    const view = (lesson: LessonSummary) => (
      <LibraryView
        lessons={[lesson]}
        folders={[]}
        folder={null}
        problem={null}
        notice={null}
        onOpen={(l) => calls.push(`open ${l.id}`)}
        onNew={noop}
        onOpenFolder={noop}
        onHome={noop}
        onNewFolder={noop}
        onRenameFolder={noop}
        onMoveFolder={noop}
        onDeleteFolder={noop}
        onRename={noop}
        onMove={noop}
        onDueDate={noop}
        onSetActive={(l, value) => calls.push(`active ${l.id} ${value}`)}
        onDelete={noop}
        onNoteChange={noop}
      />
    )
    await act(async () => root.render(view(summary({}))))
    await act(async () => container.querySelector<HTMLInputElement>('.tile-active input')!.click())
    expect(calls).toEqual(['active sample true'])
    await act(async () => root.render(view(summary({ active: true }))))
    await act(async () => container.querySelector<HTMLButtonElement>('.active-row')!.click())
    await act(async () => container.querySelector<HTMLInputElement>('.tile-active input')!.click())
    expect(calls).toEqual(['active sample true', 'open sample', 'active sample false'])
    await act(async () => root.unmount())
    container.remove()
  })
})

describe('Deadlines', () => {
  const NOW = new Date(2026, 10, 1)
  const tile = (root: HTMLElement, index = 0) => root.querySelectorAll<HTMLElement>('.tile')[index]

  it('shows a due date on a lesson tile, and a label and border when overdue', () => {
    const root = render([
      summary({ id: 'a', due_date: '2026-11-03' }),
      summary({ id: 'b', due_date: '2026-10-30', overdue: true }),
      summary({ id: 'c' })
    ])
    expect(tile(root, 0).querySelector('.due-label')?.textContent).toContain('Due Nov 3')
    expect(tile(root, 0).textContent).not.toContain('Overdue')
    expect(tile(root, 0).className).not.toContain('tile-overdue')
    expect(tile(root, 1).querySelector('.due-overdue')?.textContent).toBe('Overdue')
    expect(tile(root, 1).className).toContain('tile-overdue')
    expect(tile(root, 2).querySelector('.due-label')).toBeNull()
  })

  it('never shows a done lesson as overdue', () => {
    const root = render([summary({ due_date: '2020-01-01', done: true, problems_done: 2, overdue: false })])
    expect(root.textContent).not.toContain('Overdue')
  })

  it('shows the due date on an Active row, with the Overdue label', () => {
    const root = render([summary({ active: true, due_date: '2026-10-30', overdue: true })])
    const row = root.querySelector<HTMLElement>('.active-row')!
    expect(row.querySelector('.due-label')?.textContent).toContain('Oct 30')
    expect(row.querySelector('.due-overdue')?.textContent).toBe('Overdue')
  })

  it('shows the soonest date on a folder tile', () => {
    const root = render([], [folderOf({ id: 1, name: 'A', next_due: '2026-11-03' }), folderOf({ id: 2, name: 'B', next_due: '2026-10-01', next_due_overdue: true }), folderOf({ id: 3, name: 'C' })])
    expect(tile(root, 0).textContent).toContain('Next due Nov 3')
    expect(tile(root, 0).className).not.toContain('tile-overdue')
    expect(tile(root, 1).querySelector('.due-overdue')?.textContent).toBe('Overdue')
    expect(tile(root, 1).className).toContain('tile-overdue')
    expect(tile(root, 2).querySelector('.due-label')).toBeNull()
  })

  describe('Upcoming card', () => {
    const card = (root: HTMLElement) => root.querySelector<HTMLElement>('.upcoming-lessons')
    const rowTitles = (root: HTMLElement) => [...root.querySelectorAll('.upcoming-row .active-title')].map((e) => e.textContent)

    it('does not appear with nothing due', () => {
      expect(card(render([summary({}), summary({ id: 'b', due_date: '2026-11-03', done: true })]))).toBeNull()
    })

    it('lists unfinished lessons from any folder, soonest first, so overdue ones come first', () => {
      const physics = folderOf({ id: 1, name: 'Physics' })
      const week = folderOf({ id: 2, name: 'Week 1', parent_id: 1 })
      const root = render(
        [
          summary({ id: 'later', title: 'Later', due_date: '2026-12-01' }),
          summary({ id: 'none', title: 'None' }),
          summary({ id: 'finished', title: 'Finished', due_date: '2026-11-02', done: true }),
          summary({ id: 'late', title: 'Late', due_date: '2026-10-01', overdue: true, folder_id: 2 }),
          summary({ id: 'soon', title: 'Soon', due_date: '2026-11-03', status: 'generating' })
        ],
        [physics, week]
      )
      expect(card(root)?.querySelector('h2')?.textContent).toBe('Upcoming')
      expect(rowTitles(root)).toEqual(['Late', 'Soon', 'Later'])
      const first = root.querySelector<HTMLElement>('.upcoming-row')!
      expect(first.querySelector('.upcoming-path')?.textContent).toBe('Physics / Week 1')
      expect(first.querySelector('.due-overdue')?.textContent).toBe('Overdue')
    })

    it('comes after the Active card, on the home page only', () => {
      const lessons = [summary({ id: 'a', active: true, due_date: '2026-11-03' })]
      const root = render(lessons)
      expect(root.querySelector('.library > :nth-child(2)')?.className).toBe('active-lessons')
      expect(root.querySelector('.library > :nth-child(3)')?.className).toBe('upcoming-lessons')
      const folder = folderOf({ id: 3, name: 'Week 3' })
      expect(card(render([summary({ folder_id: 3, due_date: '2026-11-03' })], [folder], folder))).toBeNull()
    })

    it('orders lessons due the same day by when they were made', () => {
      const root = render([
        summary({ id: 'b', title: 'Newer', due_date: '2026-11-03', created: '2026-02-01' }),
        summary({ id: 'a', title: 'Older', due_date: '2026-11-03', created: '2026-01-01' })
      ])
      expect(rowTitles(root)).toEqual(['Older', 'Newer'])
    })
  })

  it('reads a date as written, whatever the time zone, with the year when it is not this one', () => {
    expect(formatDue('2026-11-01', NOW)).toBe('Nov 1')
    expect(formatDue('2026-12-31', NOW)).toBe('Dec 31')
    expect(formatDue('2027-01-01', NOW)).toBe('Jan 1, 2027')
    expect(formatDue('2025-03-09', NOW)).toBe('Mar 9, 2025')
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
    await act(async () => root.render(<LessonMenu lesson={lesson} folders={folders} onRename={noop} onMove={noop} onDueDate={noop} onDelete={noop} />))
    await act(async () => container.querySelector<HTMLButtonElement>('.tile-menu-button')!.click())
    const items = [...container.querySelectorAll<HTMLButtonElement>('[role=menuitem]')].map(
      (item) => `${item.textContent}${item.disabled ? ' (disabled)' : ''}`
    )
    await act(async () => root.unmount())
    container.remove()
    return items
  }

  it('offers rename, move, and delete when there is somewhere to move to', async () => {
    expect(await openMenu(summary({}), [WEEK3])).toEqual(['Rename', 'Move', 'Set due date', 'Delete lesson'])
    expect(await openMenu(summary({ folder_id: 3 }), [WEEK3])).toEqual(['Rename', 'Move', 'Set due date', 'Delete lesson'])
  })

  it('says Change due date once it has one', async () => {
    expect(await openMenu(summary({ due_date: '2026-11-03' }), [])).toContain('Change due date')
  })

  it('offers rename but not delete while the lesson is generating', async () => {
    expect(await openMenu(summary({ status: 'generating' }), [])).toEqual(['Rename', 'Set due date', 'Delete lesson (disabled)'])
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
      root.render(<LessonMenu lesson={summary({})} folders={[]} onRename={onRename} onMove={noop} onDueDate={noop} onDelete={noop} />)
    )
    await act(async () => container.querySelector<HTMLButtonElement>('.tile-menu-button')!.click())
    await act(async () => container.querySelector<HTMLButtonElement>('[role=menuitem]')!.click())
    expect(renamed).toBe(1)
    expect(container.querySelector('[role=menu]')).toBeNull()
    await act(async () => root.unmount())
    container.remove()
  })
})

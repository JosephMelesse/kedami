import { useEffect, useRef, useState } from 'react'
import type { Folder, LessonSummary } from '../api'

interface LessonMenuProps {
  lesson: LessonSummary
  folders: Folder[]
  onRename: () => void
  onMove: (folderId: number | null) => void
  onDelete: () => void
}

/** The options button on a lesson tile: rename it, move it to another folder or home, or delete it. */
export function LessonMenu({ lesson, folders, onRename, onMove, onDelete }: LessonMenuProps) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !root.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const choose = (action: () => void) => () => {
    setOpen(false)
    action()
  }
  const destinations = folders.filter((folder) => folder.id !== lesson.folder_id)

  return (
    <div className="tile-menu" ref={root}>
      <button
        type="button"
        className="tile-menu-button"
        aria-label={`Options for ${lesson.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        ...
      </button>
      {open && (
        <div className="menu" role="menu">
          <button type="button" role="menuitem" onClick={choose(onRename)}>
            Rename
          </button>
          {lesson.folder_id !== null && (
            <button type="button" role="menuitem" onClick={choose(() => onMove(null))}>
              Move to Lessons
            </button>
          )}
          {destinations.map((folder) => (
            <button key={folder.id} type="button" role="menuitem" onClick={choose(() => onMove(folder.id))}>
              Move to {folder.name}
            </button>
          ))}
          <button
            type="button"
            role="menuitem"
            disabled={lesson.status === 'generating'}
            title={lesson.status === 'generating' ? 'A lesson can be deleted once it finishes generating' : undefined}
            onClick={choose(onDelete)}
          >
            Delete lesson
          </button>
        </div>
      )}
    </div>
  )
}

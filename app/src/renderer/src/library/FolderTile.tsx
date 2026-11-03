import type { Folder } from '../api'
import { DueLabel } from './DueLabel'

export function FolderTile({ folder, onOpen }: { folder: Folder; onOpen: () => void }) {
  return (
    <button type="button" className={folder.next_due_overdue ? 'tile tile-folder tile-overdue' : 'tile tile-folder'} onClick={onOpen}>
      <span className="eyebrow">Folder</span>
      <span className="tile-title">{folder.name}</span>
      <DueLabel date={folder.next_due} overdue={folder.next_due_overdue} prefix="Next due" />
      <span className="muted tile-footer">
        {folder.lessons} {folder.lessons === 1 ? 'lesson' : 'lessons'}
      </span>
    </button>
  )
}

import type { Folder } from '../api'

export function FolderTile({ folder, onOpen }: { folder: Folder; onOpen: () => void }) {
  return (
    <button type="button" className="tile tile-folder" onClick={onOpen}>
      <span className="eyebrow">Folder</span>
      <span className="tile-title">{folder.name}</span>
      <span className="muted tile-footer">
        {folder.lessons} {folder.lessons === 1 ? 'lesson' : 'lessons'}
      </span>
    </button>
  )
}

import type { Folder } from '../api'

/** The folders above this one, from the top level down. */
export function foldersAbove(folders: Folder[], folder: Folder): Folder[] {
  const above: Folder[] = []
  let parent = folders.find((f) => f.id === folder.parent_id)
  while (parent) {
    above.unshift(parent)
    const next = parent.parent_id
    parent = folders.find((f) => f.id === next)
  }
  return above
}

/** A folder's full path, as in "Physics / Week 1". */
export function folderPath(folders: Folder[], folder: Folder): string {
  return [...foldersAbove(folders, folder), folder].map((f) => f.name).join(' / ')
}

/** The folder and everything inside it. */
function withDescendants(folders: Folder[], folderId: number): Set<number> {
  const found = new Set([folderId])
  for (const next of found) {
    for (const f of folders) if (f.parent_id === next) found.add(f.id)
  }
  return found
}

export interface MoveTarget {
  /** Null is the home page. */
  id: number | null
  label: string
  disabled: boolean
}

/**
 * Everywhere something can move, with each folder just above what's inside it. The current location can't be
 * picked, nor, when a folder is moving, the folder itself or anything inside it. The server refuses those too.
 */
export function moveTargets(folders: Folder[], current: number | null, moving: number | null = null): MoveTarget[] {
  const blocked = moving === null ? new Set<number>() : withDescendants(folders, moving)
  const under = (parent: number | null, prefix: string): MoveTarget[] =>
    folders
      .filter((f) => f.parent_id === parent)
      .flatMap((f) => {
        const label = prefix + f.name
        return [{ id: f.id, label, disabled: f.id === current || blocked.has(f.id) }, ...under(f.id, `${label} / `)]
      })
  return [{ id: null, label: 'Lessons', disabled: current === null }, ...under(null, '')]
}

const counted = (count: number, one: string, many: string) => (count === 1 ? `1 ${one}` : `${count} ${many}`)

/** What a folder's delete confirmation says about its contents. */
export function deleteSummary(folder: Folder, destination: string): string {
  const note = folder.note.trim() === '' ? '' : ' Its note is deleted.'
  const parts = [
    ...(folder.own_lessons > 0 ? [counted(folder.own_lessons, 'lesson', 'lessons')] : []),
    ...(folder.subfolders > 0 ? [counted(folder.subfolders, 'subfolder', 'subfolders')] : [])
  ]
  if (parts.length === 0) return `The folder is empty.${note}`
  const verb = folder.own_lessons + folder.subfolders === 1 ? 'moves' : 'move'
  return `Its ${parts.join(' and ')} ${verb} up to ${destination}.${note}`
}

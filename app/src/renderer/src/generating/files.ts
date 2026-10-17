// The file types a lesson can be made from. Mirrors server/kedami_server/generation/sources.py.

export type FileKind = 'text' | 'image' | 'pdf'

const KINDS: Record<string, FileKind> = {
  '.txt': 'text',
  '.md': 'text',
  '.markdown': 'text',
  '.png': 'image',
  '.jpg': 'image',
  '.jpeg': 'image',
  '.webp': 'image',
  '.gif': 'image',
  '.pdf': 'pdf'
}

export const ACCEPT = Object.keys(KINDS).join(',')

// A SQL lesson's course database: a SQLite file or a SQL script. See Course databases in architecture/sql-lessons.md.
const DATABASE_EXTENSIONS = ['.sqlite', '.db', '.sql']

export const DATABASE_ACCEPT = DATABASE_EXTENSIONS.join(',')

export function isDatabaseFile(filename: string): boolean {
  const dot = filename.lastIndexOf('.')
  return dot >= 0 && DATABASE_EXTENSIONS.includes(filename.slice(dot).toLowerCase())
}

export function kindOf(filename: string): FileKind | null {
  const dot = filename.lastIndexOf('.')
  return dot < 0 ? null : (KINDS[filename.slice(dot).toLowerCase()] ?? null)
}

/** Force transcription only applies to files with page images. */
export function canForce(filename: string): boolean {
  const kind = kindOf(filename)
  return kind === 'pdf' || kind === 'image'
}

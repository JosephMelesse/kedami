// Music player tracks: audio files copied into the data folder's music/, served to the
// renderer by file name. Nothing outside that folder can be named or served.
import { constants, createReadStream } from 'node:fs'
import { copyFile, mkdir, readdir, realpath, stat } from 'node:fs/promises'
import { basename, extname, join, parse, sep } from 'node:path'
import { Readable } from 'node:stream'

export const MUSIC_SCHEME = 'kedami-music'
export const MUSIC_EXTENSIONS = ['mp3', 'm4a', 'flac', 'wav', 'ogg']

const MAX_NAME = 255

/** True for a plain file name, with no folder part, that has a supported audio extension. */
export function isTrackName(name: unknown): name is string {
  if (typeof name !== 'string' || name.length === 0 || name.length > MAX_NAME) return false
  if (name.startsWith('.') || /[/\\\0]/.test(name)) return false
  return MUSIC_EXTENSIONS.includes(extname(name).slice(1).toLowerCase())
}

/** The audio files directly inside the folder, by name with numbers in order. */
export async function listTracks(dir: string): Promise<string[]> {
  let entries
  try {
    entries = await readdir(dir, { withFileTypes: true })
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
    throw error
  }
  return entries
    .filter((entry) => (entry.isFile() || entry.isSymbolicLink()) && isTrackName(entry.name))
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }))
}

/** Copy an audio file into the folder, renaming it "name (2).ext" and so on if the name is taken. */
export async function addTrack(dir: string, source: string): Promise<string> {
  const original = basename(source)
  if (!isTrackName(original)) throw new Error(`Not a supported audio file: ${original}`)
  await mkdir(dir, { recursive: true })
  const { name, ext } = parse(original)
  for (let n = 1; ; n++) {
    const candidate = n === 1 ? original : `${name} (${n})${ext}`
    try {
      await copyFile(source, join(dir, candidate), constants.COPYFILE_EXCL)
      return candidate
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error
    }
  }
}

/** The track's real path, or null unless it is a supported file that resolves inside the folder. */
export async function resolveTrack(dir: string, name: unknown): Promise<string | null> {
  if (!isTrackName(name)) return null
  try {
    const root = await realpath(dir)
    const path = await realpath(join(dir, name))
    return path.startsWith(root + sep) && isTrackName(basename(path)) ? path : null
  } catch {
    return null
  }
}

/** The renderer's URL for a track. */
export function trackUrl(name: string): string {
  return `${MUSIC_SCHEME}://track/${encodeURIComponent(name)}`
}

/** The track name a music URL asks for, or null if it isn't one. */
export function trackNameFromUrl(url: string): string | null {
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return null
  }
  if (parsed.protocol !== `${MUSIC_SCHEME}:` || parsed.host !== 'track') return null
  if (parsed.search || parsed.hash) return null
  const encoded = parsed.pathname.slice(1)
  if (encoded.includes('/')) return null
  try {
    const name = decodeURIComponent(encoded)
    return isTrackName(name) ? name : null
  } catch {
    return null
  }
}

const CONTENT_TYPES: Record<string, string> = {
  mp3: 'audio/mpeg',
  m4a: 'audio/mp4',
  flac: 'audio/flac',
  wav: 'audio/wav',
  ogg: 'audio/ogg'
}

export function contentType(name: string): string {
  return CONTENT_TYPES[extname(name).slice(1).toLowerCase()] ?? 'application/octet-stream'
}

/**
 * The inclusive byte range a Range header asks for: null for the whole file (no header, or a
 * form not handled here such as several ranges), or 'unsatisfiable' for a range past the end.
 */
export function parseRange(
  header: string | null,
  size: number
): { start: number; end: number } | null | 'unsatisfiable' {
  const match = header?.trim().match(/^bytes=(\d*)-(\d*)$/)
  if (!match || (match[1] === '' && match[2] === '')) return null
  if (match[1] === '') {
    const suffix = Number(match[2])
    if (suffix === 0 || size === 0) return 'unsatisfiable'
    return { start: Math.max(0, size - suffix), end: size - 1 }
  }
  const start = Number(match[1])
  const end = match[2] === '' ? size - 1 : Math.min(Number(match[2]), size - 1)
  if (start >= size || end < start) return 'unsatisfiable'
  return { start, end }
}

/** A track's bytes, honoring a single Range request so audio elements can seek and loop. */
export async function trackResponse(path: string, rangeHeader: string | null): Promise<Response> {
  const { size } = await stat(path)
  const range = parseRange(rangeHeader, size)
  const headers = { 'Content-Type': contentType(path), 'Accept-Ranges': 'bytes' }
  if (range === 'unsatisfiable') {
    return new Response(null, { status: 416, headers: { ...headers, 'Content-Range': `bytes */${size}` } })
  }
  const { start, end } = range ?? { start: 0, end: size - 1 }
  const body = size === 0 ? null : (Readable.toWeb(createReadStream(path, { start, end })) as ReadableStream)
  return new Response(body, {
    status: range ? 206 : 200,
    headers: {
      ...headers,
      'Content-Length': String(size === 0 ? 0 : end - start + 1),
      ...(range && { 'Content-Range': `bytes ${start}-${end}/${size}` })
    }
  })
}

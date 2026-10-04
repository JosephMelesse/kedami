import { mkdir, mkdtemp, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  addTrack,
  contentType,
  isTrackName,
  listTracks,
  parseRange,
  resolveTrack,
  trackNameFromUrl,
  trackResponse,
  trackUrl
} from '../src/main/music'

let root: string
let music: string

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), 'kedami-music-'))
  music = join(root, 'music')
})

afterEach(() => rm(root, { recursive: true, force: true }))

async function file(path: string, contents = 'audio'): Promise<string> {
  await writeFile(path, contents)
  return path
}

describe('isTrackName', () => {
  it.each(['song.mp3', 'Song.MP3', 'a b (2).m4a', 'x.flac', 'x.wav', 'x.ogg', 'ሙዚቃ.mp3'])('accepts %s', (name) => {
    expect(isTrackName(name)).toBe(true)
  })

  it.each([
    '',
    'song',
    'song.txt',
    'song.mp3.exe',
    '.hidden.mp3',
    '..',
    '../song.mp3',
    'sub/song.mp3',
    'sub\\song.mp3',
    'song\0.mp3',
    `${'a'.repeat(252)}.mp3`,
    42,
    null
  ])('refuses %s', (name) => {
    expect(isTrackName(name)).toBe(false)
  })
})

describe('listTracks', () => {
  it('is empty before the folder exists', async () => {
    expect(await listTracks(music)).toEqual([])
  })

  it('lists audio files only, numbers in order, skipping subfolders', async () => {
    await mkdir(join(music, 'sub.mp3'), { recursive: true })
    await file(join(music, 'sub.mp3', 'inner.mp3'))
    for (const name of ['track 10.mp3', 'track 2.mp3', 'Alpha.ogg', 'notes.txt', '.hidden.mp3']) {
      await file(join(music, name))
    }
    expect(await listTracks(music)).toEqual(['Alpha.ogg', 'track 2.mp3', 'track 10.mp3'])
  })
})

describe('addTrack', () => {
  it('copies the file in, creating the folder', async () => {
    const source = await file(join(root, 'song.mp3'), 'one')
    expect(await addTrack(music, source)).toBe('song.mp3')
    expect(await readFile(join(music, 'song.mp3'), 'utf8')).toBe('one')
  })

  it('numbers a taken name instead of overwriting', async () => {
    const source = await file(join(root, 'song.mp3'), 'one')
    await addTrack(music, source)
    await writeFile(source, 'two')
    expect(await addTrack(music, source)).toBe('song (2).mp3')
    await writeFile(source, 'three')
    expect(await addTrack(music, source)).toBe('song (3).mp3')
    expect(await readFile(join(music, 'song.mp3'), 'utf8')).toBe('one')
    expect(await readFile(join(music, 'song (2).mp3'), 'utf8')).toBe('two')
    expect(await listTracks(music)).toEqual(['song (2).mp3', 'song (3).mp3', 'song.mp3'])
  })

  it('refuses files that are not audio', async () => {
    const source = await file(join(root, 'notes.txt'))
    await expect(addTrack(music, source)).rejects.toThrow('Not a supported audio file')
    expect(await readdir(root)).not.toContain('music')
  })
})

describe('resolveTrack', () => {
  beforeEach(async () => {
    await mkdir(music)
    await file(join(music, 'song.mp3'))
  })

  it('resolves a track in the folder', async () => {
    expect(await resolveTrack(music, 'song.mp3')).toBe(join(music, 'song.mp3'))
  })

  it.each(['missing.mp3', '../outside.mp3', '..%2Foutside.mp3', '', 'song', 42])('refuses %s', async (name) => {
    await file(join(root, 'outside.mp3'))
    expect(await resolveTrack(music, name)).toBeNull()
  })

  it('refuses a symlink that leaves the folder', async () => {
    await symlink(await file(join(root, 'outside.mp3')), join(music, 'escape.mp3'))
    expect(await resolveTrack(music, 'escape.mp3')).toBeNull()
  })

  it('refuses a symlink to a non-audio file inside the folder', async () => {
    await file(join(music, 'notes.txt'))
    await symlink(join(music, 'notes.txt'), join(music, 'notes.mp3'))
    expect(await resolveTrack(music, 'notes.mp3')).toBeNull()
  })

  it('follows a symlink that stays inside the folder', async () => {
    await symlink(join(music, 'song.mp3'), join(music, 'alias.mp3'))
    expect(await resolveTrack(music, 'alias.mp3')).toBe(join(music, 'song.mp3'))
  })

  it('works when the folder itself is reached through a symlink', async () => {
    const linked = join(root, 'linked')
    await symlink(music, linked)
    expect(await resolveTrack(linked, 'song.mp3')).toBe(join(music, 'song.mp3'))
  })
})

describe('track URLs', () => {
  it.each(['song.mp3', 'a b (2).m4a', 'ሙዚቃ #1?.flac', '100%.wav'])('round-trips %s', (name) => {
    expect(trackNameFromUrl(trackUrl(name))).toBe(name)
  })

  it('collapses dot segments before reading the name, so they cannot leave the track path', () => {
    expect(trackNameFromUrl('kedami-music://track/../../song.mp3')).toBe('song.mp3')
  })

  it.each([
    'kedami-music://track/..%2Fsecret.mp3',
    'kedami-music://track/sub/song.mp3',
    'kedami-music://other/song.mp3',
    'kedami-music://track/song.mp3?x=1',
    'kedami-music://track/song.txt',
    'kedami-music://track/%E0%A4%A.mp3',
    'file:///home/me/song.mp3',
    'not a url'
  ])('refuses %s', (url) => {
    expect(trackNameFromUrl(url)).toBeNull()
  })
})

describe('parseRange', () => {
  it.each([
    [null, null],
    ['', null],
    ['bytes=0-0,5-9', null],
    ['items=0-9', null],
    ['bytes=-', null],
    ['bytes=0-', { start: 0, end: 99 }],
    ['bytes=10-19', { start: 10, end: 19 }],
    ['bytes=90-500', { start: 90, end: 99 }],
    ['bytes=99-99', { start: 99, end: 99 }],
    ['bytes=-10', { start: 90, end: 99 }],
    ['bytes=-500', { start: 0, end: 99 }],
    ['bytes=100-', 'unsatisfiable'],
    ['bytes=20-10', 'unsatisfiable'],
    ['bytes=-0', 'unsatisfiable']
  ])('reads %s of 100 bytes', (header, range) => {
    expect(parseRange(header, 100)).toEqual(range)
  })

  it('has nothing to give from an empty file', () => {
    expect(parseRange('bytes=0-', 0)).toBe('unsatisfiable')
    expect(parseRange('bytes=-5', 0)).toBe('unsatisfiable')
  })
})

describe('contentType', () => {
  it.each([
    ['a.mp3', 'audio/mpeg'],
    ['a.M4A', 'audio/mp4'],
    ['a.flac', 'audio/flac'],
    ['a.wav', 'audio/wav'],
    ['a.ogg', 'audio/ogg']
  ])('%s is %s', (name, type) => {
    expect(contentType(name)).toBe(type)
  })
})

describe('trackResponse', () => {
  let path: string
  beforeEach(async () => {
    path = await file(join(root, 'song.mp3'), '0123456789')
  })

  it('sends the whole file without a range', async () => {
    const response = await trackResponse(path, null)
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('audio/mpeg')
    expect(response.headers.get('accept-ranges')).toBe('bytes')
    expect(response.headers.get('content-length')).toBe('10')
    expect(await response.text()).toBe('0123456789')
  })

  it('sends the requested bytes', async () => {
    const response = await trackResponse(path, 'bytes=2-5')
    expect(response.status).toBe(206)
    expect(response.headers.get('content-range')).toBe('bytes 2-5/10')
    expect(response.headers.get('content-length')).toBe('4')
    expect(await response.text()).toBe('2345')
  })

  it('refuses a range past the end', async () => {
    const response = await trackResponse(path, 'bytes=10-')
    expect(response.status).toBe(416)
    expect(response.headers.get('content-range')).toBe('bytes */10')
  })

  it('handles an empty file', async () => {
    const empty = await file(join(root, 'empty.mp3'), '')
    const response = await trackResponse(empty, null)
    expect(response.status).toBe(200)
    expect(await response.text()).toBe('')
  })
})

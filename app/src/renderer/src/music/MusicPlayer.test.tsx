import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import type { KedamiApi, MusicTrack } from '../../../preload/api'
import { MusicPlayer } from './MusicPlayer'

function track(name: string): MusicTrack {
  return { name, url: `kedami-music://track/${encodeURIComponent(name)}` }
}

let container: HTMLDivElement
let root: Root
let play: Mock<() => Promise<void>>
let pause: Mock<() => void>

beforeEach(() => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  play = vi.fn(() => Promise.resolve())
  pause = vi.fn(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(play)
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(pause)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.restoreAllMocks()
})

async function mount(tracks: MusicTrack[], addMusic: KedamiApi['addMusic'] = vi.fn()): Promise<void> {
  window.kedami = { musicTracks: async () => tracks, addMusic } as unknown as KedamiApi
  await act(async () => root.render(<MusicPlayer />))
}

const select = () => container.querySelector('select')!
const toggle = () => container.querySelector('button')!
const audio = () => container.querySelector('audio')

async function choose(value: string): Promise<void> {
  await act(async () => {
    select().value = value
    select().dispatchEvent(new Event('change', { bubbles: true }))
  })
}

describe('MusicPlayer', () => {
  it('has nothing to play before music is added', async () => {
    await mount([])
    expect([...select().options].map((o) => [o.textContent, o.disabled])).toEqual([
      ['No music yet', true],
      ['Add music', false]
    ])
    expect(select().value).toBe('')
    expect(toggle().getAttribute('aria-label')).toBe('Play')
    expect(toggle().disabled).toBe(true)
    expect(audio()).toBeNull()
  })

  it('lists tracks with Add music last, and selects the first track, on repeat', async () => {
    await mount([track('a.mp3'), track('b.ogg')])
    expect([...select().options].map((o) => o.textContent)).toEqual(['a.mp3', 'b.ogg', 'Add music'])
    expect(select().value).toBe('a.mp3')
    expect(audio()?.getAttribute('src')).toBe('kedami-music://track/a.mp3')
    expect(audio()?.loop).toBe(true)
  })

  it('plays and pauses, showing the symbol for what a click does', async () => {
    await mount([track('a.mp3')])
    expect([toggle().textContent, toggle().getAttribute('aria-label')]).toEqual(['\u25B6\uFE0E', 'Play'])
    await act(async () => toggle().click())
    expect(play).toHaveBeenCalledTimes(1)
    expect([toggle().textContent, toggle().getAttribute('aria-label')]).toEqual(['\u23F8\uFE0E', 'Pause'])
    await act(async () => toggle().click())
    expect(pause).toHaveBeenCalled()
    expect(toggle().getAttribute('aria-label')).toBe('Play')
  })

  it('marks the track name as playing only while it plays', async () => {
    await mount([track('a.mp3')])
    expect(select().classList.contains('playing')).toBe(false)
    await act(async () => toggle().click())
    expect(select().classList.contains('playing')).toBe(true)
    await act(async () => toggle().click())
    expect(select().classList.contains('playing')).toBe(false)
  })

  it('keeps playing when another track is picked', async () => {
    await mount([track('a.mp3'), track('b.ogg')])
    await act(async () => toggle().click())
    await choose('b.ogg')
    expect(audio()?.getAttribute('src')).toBe('kedami-music://track/b.ogg')
    expect(play).toHaveBeenCalledTimes(2)
    expect(toggle().getAttribute('aria-label')).toBe('Pause')
  })

  it('stops when a track fails to play', async () => {
    await mount([track('broken.mp3')])
    play.mockImplementation(() => Promise.reject(new DOMException('no', 'NotSupportedError')))
    await act(async () => toggle().click())
    expect(toggle().getAttribute('aria-label')).toBe('Play')
  })

  it('pauses during rest with play disabled, then resumes if it was playing', async () => {
    await mount([track('a.mp3')])
    await act(async () => toggle().click())
    expect(toggle().getAttribute('aria-label')).toBe('Pause')

    pause.mockClear()
    await act(async () => root.render(<MusicPlayer resting />))
    expect(pause).toHaveBeenCalledTimes(1)
    expect(toggle().getAttribute('aria-label')).toBe('Play')
    expect(toggle().disabled).toBe(true)

    play.mockClear()
    await act(async () => root.render(<MusicPlayer resting={false} />))
    expect(toggle().disabled).toBe(false)
    expect(play).toHaveBeenCalledTimes(1)
    expect(toggle().getAttribute('aria-label')).toBe('Pause')
  })

  it('stays paused after rest if it was paused before', async () => {
    await mount([track('a.mp3')])
    await act(async () => root.render(<MusicPlayer resting />))
    await act(async () => root.render(<MusicPlayer resting={false} />))
    expect(play).not.toHaveBeenCalled()
    expect(toggle().getAttribute('aria-label')).toBe('Play')
  })

  it('adds music from the last entry and selects the first added track', async () => {
    const addMusic = vi.fn(async () => ({ tracks: [track('a.mp3'), track('new.mp3')], added: ['new.mp3'] }))
    await mount([track('a.mp3')], addMusic)
    await choose('add-music')
    expect(addMusic).toHaveBeenCalledTimes(1)
    expect(select().value).toBe('new.mp3')
  })

  it('adds the first music from an empty list', async () => {
    const addMusic = vi.fn(async () => ({ tracks: [track('new.mp3')], added: ['new.mp3'] }))
    await mount([], addMusic)
    await choose('add-music')
    expect([...select().options].map((o) => o.textContent)).toEqual(['new.mp3', 'Add music'])
    expect(select().value).toBe('new.mp3')
    expect(toggle().disabled).toBe(false)
  })

  it('keeps the selection when the picker is canceled', async () => {
    const addMusic = vi.fn(async () => ({ tracks: [track('a.mp3'), track('b.mp3')], added: [] }))
    await mount([track('a.mp3'), track('b.mp3')], addMusic)
    await choose('b.mp3')
    await choose('add-music')
    expect(addMusic).toHaveBeenCalledTimes(1)
    expect(select().value).toBe('b.mp3')
  })
})

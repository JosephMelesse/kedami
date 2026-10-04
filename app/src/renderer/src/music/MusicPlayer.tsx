import { useEffect, useRef, useState } from 'react'
import type { MusicTrack } from '../../../preload/api'

// The last entry in the track list opens the file picker. It has no audio extension, so no track can share it.
const ADD_MUSIC = 'add-music'
// The text variation selector (U+FE0E) keeps the symbols from turning into color emoji.
const PLAY_SYMBOL = '\u25B6\uFE0E'
const PAUSE_SYMBOL = '\u23F8\uFE0E'

/** A track picker and play button. The selected track repeats until paused or changed. */
export function MusicPlayer() {
  const [tracks, setTracks] = useState<MusicTrack[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const audio = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    window.kedami
      .musicTracks()
      .then((list) => {
        setTracks(list)
        setSelected((current) => current ?? list[0]?.name ?? null)
      })
      .catch(() => {})
  }, [])

  // Runs after the new src is in place, so picking a track while playing switches to it.
  // A switch aborts the previous play request; only other failures stop the player.
  useEffect(() => {
    const element = audio.current
    if (!element) return
    if (playing && selected) {
      element.play()?.catch((error: DOMException) => {
        if (error.name !== 'AbortError') setPlaying(false)
      })
    } else {
      element.pause()
    }
  }, [playing, selected])

  const add = async () => {
    try {
      const result = await window.kedami.addMusic()
      setTracks(result.tracks)
      if (result.added.length > 0) setSelected(result.added[0])
    } catch {
      // A failed copy leaves the list as it was.
    }
  }

  const track = tracks.find((t) => t.name === selected)
  return (
    <div className="music-player">
      <select
        className={playing ? 'music-select playing' : 'music-select'}
        aria-label="Track"
        value={selected ?? ''}
        onChange={(event) => {
          // Choosing Add music leaves the selection as it was; the controlled value snaps back.
          if (event.target.value === ADD_MUSIC) add()
          else setSelected(event.target.value)
        }}
      >
        {tracks.length === 0 && (
          <option value="" disabled>
            No music yet
          </option>
        )}
        {tracks.map((t) => (
          <option key={t.name} value={t.name}>
            {t.name}
          </option>
        ))}
        <option value={ADD_MUSIC}>Add music</option>
      </select>
      <button
        type="button"
        className="button music-toggle"
        aria-label={playing ? 'Pause' : 'Play'}
        disabled={!track}
        onClick={() => setPlaying(!playing)}
      >
        {playing ? PAUSE_SYMBOL : PLAY_SYMBOL}
      </button>
      {track && <audio ref={audio} src={track.url} loop onError={() => setPlaying(false)} />}
    </div>
  )
}

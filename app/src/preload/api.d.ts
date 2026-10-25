// What the preload exposes to the renderer as window.kedami.
export interface ServerConnection {
  baseUrl: string
  token: string
}

export interface MusicTrack {
  /** The file name in the data folder's music/. */
  name: string
  /** Where the renderer loads it from. */
  url: string
}

export interface KedamiApi {
  serverConnection(): Promise<ServerConnection>
  /** The music player's tracks, by name. */
  musicTracks(): Promise<MusicTrack[]>
  /** Pick audio files and copy them into the music folder. Returns the new list and the added names. */
  addMusic(): Promise<{ tracks: MusicTrack[]; added: string[] }>
  /** Lay the Terminal panel's view over this rectangle of the window, in CSS pixels. */
  showTerminal(bounds: { x: number; y: number; width: number; height: number }): void
  /** Hide the Terminal panel's view. Its session keeps running. */
  hideTerminal(): void
  /** Calls the listener on Ctrl+` (Cmd+` on macOS), wherever the keyboard is. Returns a function that stops it. */
  onTerminalToggle(listener: () => void): () => void
}

declare global {
  interface Window {
    kedami: KedamiApi
  }
}

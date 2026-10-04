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
  /** Open a LeetCode problem in the default browser. */
  openLeetCode(slug: string): Promise<void>
  /** The music player's tracks, by name. */
  musicTracks(): Promise<MusicTrack[]>
  /** Pick audio files and copy them into the music folder. Returns the new list and the added names. */
  addMusic(): Promise<{ tracks: MusicTrack[]; added: string[] }>
}

declare global {
  interface Window {
    kedami: KedamiApi
  }
}

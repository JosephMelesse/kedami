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
  /** Open a pgexercises page, named by its section and page, such as "joins/self2.html". */
  openPgExercises(path: string): Promise<void>
  /** The music player's tracks, by name. */
  musicTracks(): Promise<MusicTrack[]>
  /** Pick audio files and copy them into the music folder. Returns the new list and the added names. */
  addMusic(): Promise<{ tracks: MusicTrack[]; added: string[] }>
  /** Pyodide's binaries for the code runner, which its frame can't load itself. */
  runnerFiles(): Promise<{ wasm: ArrayBuffer; stdlib: ArrayBuffer }>
  /** Lay the Terminal screen's view over this rectangle of the window, in CSS pixels. */
  showTerminal(bounds: { x: number; y: number; width: number; height: number }): void
  /** Hide the Terminal screen's view. Its session keeps running. */
  hideTerminal(): void
}

declare global {
  interface Window {
    kedami: KedamiApi
  }
}

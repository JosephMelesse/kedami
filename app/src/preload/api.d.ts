// What the preload exposes to the renderer as window.kedami.
export interface ServerConnection {
  baseUrl: string
  token: string
}

export interface KedamiApi {
  serverConnection(): Promise<ServerConnection>
  /** Open a LeetCode problem in the default browser. */
  openLeetCode(slug: string): Promise<void>
}

declare global {
  interface Window {
    kedami: KedamiApi
  }
}

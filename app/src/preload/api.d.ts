// What the preload exposes to the renderer as window.kedami.
export interface ServerConnection {
  baseUrl: string
  token: string
}

export interface KedamiApi {
  serverConnection(): Promise<ServerConnection>
}

declare global {
  interface Window {
    kedami: KedamiApi
  }
}

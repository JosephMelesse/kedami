// What the terminal view's preload exposes as window.terminal. Only that view gets it.
export type SessionKind = 'claude' | 'shell'

export interface TerminalApi {
  /** The running session, and whether Claude Code is installed. */
  state(): Promise<{ running: SessionKind | null; claude: boolean }>
  /** Start a session at this size unless one is running. Resolves to what is running afterwards. */
  start(kind: SessionKind, cols: number, rows: number): Promise<{ running: SessionKind | null }>
  /** Keystrokes and pasted text. */
  input(data: string): void
  resize(cols: number, rows: number): void
  onData(listener: (data: string) => void): void
  /** The session ended, with its exit code. */
  onExit(listener: (code: number) => void): void
  /** The panel was shown; a session starts then if none is running. */
  onShown(listener: () => void): void
}

declare global {
  interface Window {
    terminal: TerminalApi
  }
}

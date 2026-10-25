// The Terminal screen's pseudo-terminal: one session at a time, Claude Code or the student's shell.
// The terminal can run anything as the student, so only the terminal view may start a session, type,
// or resize; every message from any other sender is dropped. See architecture/agent-mode.md, Isolation.
import { accessSync, constants, statSync } from 'node:fs'
import { delimiter as posixDelimiter, join } from 'node:path'

export type SessionKind = 'claude' | 'shell'

const KINDS: readonly SessionKind[] = ['claude', 'shell']
// Generous limits on a terminal's size, so a bad message can't ask for a huge buffer.
const MAX_COLS = 1000
const MAX_ROWS = 500

/** The parts of a node-pty process the hub uses, so tests can stand in for it. */
export interface Pty {
  write(data: string): void
  resize(cols: number, rows: number): void
  kill(): void
  onData(listener: (data: string) => void): void
  onExit(listener: (code: number) => void): void
}

export interface SessionCommand {
  file: string
  args: string[]
  cwd: string
  env: Record<string, string>
}

interface CommandOptions {
  dataDir: string
  env: Record<string, string | undefined>
  /** Where Claude Code is installed, or null if it isn't on the path. */
  claude: string | null
  platform: NodeJS.Platform
  port: number
  token: string
}

/** What to run for a session, or null when it can't run. Claude Code starts with Kedami's plugin; both
 * start in the data folder, with the server's port and token so the plugin's MCP server can reach it. */
export function sessionCommand(kind: SessionKind, options: CommandOptions): SessionCommand | null {
  const env: Record<string, string> = {}
  for (const [key, value] of Object.entries(options.env)) if (value !== undefined) env[key] = value
  env.KEDAMI_PORT = String(options.port)
  env.KEDAMI_TOKEN = options.token
  const base = { cwd: options.dataDir, env }
  if (kind === 'claude') {
    if (!options.claude) return null
    return { ...base, file: options.claude, args: ['--plugin-dir', join(options.dataDir, 'agent-plugin')] }
  }
  const windows = options.platform === 'win32'
  const shell = windows ? options.env.COMSPEC || 'cmd.exe' : options.env.SHELL || '/bin/bash'
  return { ...base, file: shell, args: [] }
}

/** The first executable named `name` in a PATH, or null. On Windows, each of PATHEXT's extensions is tried. */
export function findOnPath(
  name: string,
  path: string,
  platform: NodeJS.Platform,
  pathExt = '.COM;.EXE;.BAT;.CMD'
): string | null {
  const windows = platform === 'win32'
  const names = windows ? ['', ...pathExt.split(';')].map((ext) => name + ext.toLowerCase()) : [name]
  for (const dir of path.split(windows ? ';' : posixDelimiter)) {
    if (!dir) continue
    for (const candidate of names) {
      const full = join(dir, candidate)
      try {
        if (!statSync(full).isFile()) continue
        if (!windows) accessSync(full, constants.X_OK)
        return full
      } catch {
        // Missing, or not executable: try the next one.
      }
    }
  }
  return null
}

/** The keys Electron reports for a keystroke, as in its before-input-event. */
export interface KeyInput {
  type: string
  key: string
  control: boolean
  meta: boolean
  alt: boolean
}

/** Ctrl+` (Cmd+` on macOS), which opens and closes the Terminal panel from anywhere in the app. */
export function isToggleShortcut(input: KeyInput, platform: NodeJS.Platform): boolean {
  const modifier = platform === 'darwin' ? input.meta : input.control
  return input.type === 'keyDown' && input.key === '`' && modifier && !input.alt
}

interface HubOptions {
  /** Whether a message came from the terminal view. */
  isTerminal: (sender: unknown) => boolean
  command: (kind: SessionKind) => SessionCommand | null
  spawn: (command: SessionCommand, cols: number, rows: number) => Pty
  /** Sends to the terminal view only. */
  send: (channel: 'terminal:data' | 'terminal:exit', value: unknown) => void
}

export class TerminalHub {
  private session: { kind: SessionKind; pty: Pty } | null = null

  constructor(private readonly options: HubOptions) {}

  /** What the terminal view shows: the running session, and whether Claude Code can start. Null to anyone else. */
  state(sender: unknown): { running: SessionKind | null; claude: boolean } | null {
    if (!this.options.isTerminal(sender)) return null
    return { running: this.session?.kind ?? null, claude: this.options.command('claude') !== null }
  }

  /** Start a session unless one is running. Returns what is running afterwards; null to anyone else. */
  start(sender: unknown, kind: SessionKind, cols: number, rows: number): { running: SessionKind | null } | null {
    if (!this.options.isTerminal(sender)) return null
    if (this.session || !KINDS.includes(kind) || !validSize(cols, rows)) return { running: this.session?.kind ?? null }
    const command = this.options.command(kind)
    if (!command) return { running: null }
    const pty = this.options.spawn(command, cols, rows)
    const session = { kind, pty }
    this.session = session
    pty.onData((data) => this.options.send('terminal:data', data))
    pty.onExit((code) => {
      if (this.session === session) this.session = null
      this.options.send('terminal:exit', code)
    })
    return { running: kind }
  }

  input(sender: unknown, data: unknown): void {
    if (this.options.isTerminal(sender) && typeof data === 'string') this.session?.pty.write(data)
  }

  resize(sender: unknown, cols: unknown, rows: unknown): void {
    if (this.options.isTerminal(sender) && validSize(cols, rows)) this.session?.pty.resize(cols, rows as number)
  }

  dispose(): void {
    this.session?.pty.kill()
    this.session = null
  }
}

function validSize(cols: unknown, rows: unknown): cols is number {
  const ok = (n: unknown, max: number) => Number.isInteger(n) && (n as number) >= 1 && (n as number) <= max
  return ok(cols, MAX_COLS) && ok(rows, MAX_ROWS)
}

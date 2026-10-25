import { chmodSync, mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { beforeEach, describe, expect, it } from 'vitest'
import { findOnPath, type Pty, sessionCommand, TerminalHub } from '../src/main/terminal'

class FakePty implements Pty {
  written: string[] = []
  size = { cols: 0, rows: 0 }
  killed = false
  private dataListener: (data: string) => void = () => {}
  private exitListener: (code: number) => void = () => {}
  write(data: string) {
    this.written.push(data)
  }
  resize(cols: number, rows: number) {
    this.size = { cols, rows }
  }
  kill() {
    this.killed = true
  }
  onData(listener: (data: string) => void) {
    this.dataListener = listener
  }
  onExit(listener: (code: number) => void) {
    this.exitListener = listener
  }
  emit(data: string) {
    this.dataListener(data)
  }
  exit(code: number) {
    this.exitListener(code)
  }
}

const TERMINAL = { id: 'terminal view' }
const LESSON_WINDOW = { id: 'lesson window' }

let spawned: { command: ReturnType<typeof sessionCommand>; pty: FakePty }[]
let sent: { channel: string; value: unknown }[]
let hub: TerminalHub

beforeEach(() => {
  spawned = []
  sent = []
  hub = new TerminalHub({
    isTerminal: (sender) => sender === TERMINAL,
    command: (kind) => sessionCommand(kind, { dataDir: '/data', env: { PATH: '/bin', SHELL: '/bin/zsh' }, claude: '/bin/claude', platform: 'linux', port: 8765, token: 'secret' }),
    spawn: (command) => {
      const pty = new FakePty()
      spawned.push({ command, pty })
      return pty
    },
    send: (channel, value) => sent.push({ channel, value })
  })
})

describe('the terminal gate', () => {
  it('starts a session, passes keystrokes and resizes, and forwards output, for the terminal view', () => {
    expect(hub.start(TERMINAL, 'shell', 80, 24)).toEqual({ running: 'shell' })
    hub.input(TERMINAL, 'ls\r')
    hub.resize(TERMINAL, 100, 30)
    spawned[0].pty.emit('file.txt')
    expect(spawned[0].pty.written).toEqual(['ls\r'])
    expect(spawned[0].pty.size).toEqual({ cols: 100, rows: 30 })
    expect(sent).toEqual([{ channel: 'terminal:data', value: 'file.txt' }])
  })

  it('drops every message from the lesson window', () => {
    expect(hub.start(LESSON_WINDOW, 'shell', 80, 24)).toBeNull()
    expect(spawned).toEqual([])
    hub.start(TERMINAL, 'shell', 80, 24)
    hub.input(LESSON_WINDOW, 'rm -rf ~\r')
    hub.resize(LESSON_WINDOW, 1, 1)
    expect(spawned[0].pty.written).toEqual([])
    expect(spawned[0].pty.size).toEqual({ cols: 0, rows: 0 })
    expect(hub.state(LESSON_WINDOW)).toBeNull()
  })

  it('runs one session at a time and frees the slot when it exits', () => {
    hub.start(TERMINAL, 'shell', 80, 24)
    expect(hub.start(TERMINAL, 'claude', 80, 24)).toEqual({ running: 'shell' })
    expect(spawned).toHaveLength(1)
    spawned[0].pty.exit(0)
    expect(sent).toContainEqual({ channel: 'terminal:exit', value: 0 })
    expect(hub.state(TERMINAL)).toEqual({ running: null, claude: true })
    hub.start(TERMINAL, 'claude', 80, 24)
    expect(spawned).toHaveLength(2)
  })

  it('ignores input of the wrong type and sizes out of range', () => {
    hub.start(TERMINAL, 'shell', 80, 24)
    hub.input(TERMINAL, 42 as unknown as string)
    hub.resize(TERMINAL, 0, 24)
    hub.resize(TERMINAL, 80, 100_000)
    expect(spawned[0].pty.written).toEqual([])
    expect(spawned[0].pty.size).toEqual({ cols: 0, rows: 0 })
    expect(hub.start(TERMINAL, 'python' as 'shell', 80, 24)).toEqual({ running: 'shell' })
  })

  it('kills the session when the app closes', () => {
    hub.start(TERMINAL, 'shell', 80, 24)
    hub.dispose()
    expect(spawned[0].pty.killed).toBe(true)
  })

  it('says when Claude Code is missing, and refuses to start it', () => {
    const missing = new TerminalHub({
      isTerminal: (sender) => sender === TERMINAL,
      command: (kind) => sessionCommand(kind, { dataDir: '/data', env: {}, claude: null, platform: 'linux', port: 1, token: 't' }),
      spawn: () => new FakePty(),
      send: () => {}
    })
    expect(missing.state(TERMINAL)).toEqual({ running: null, claude: false })
    expect(missing.start(TERMINAL, 'claude', 80, 24)).toEqual({ running: null })
  })
})

describe('session commands', () => {
  const options = { dataDir: '/data', env: { PATH: '/bin', SHELL: '/bin/zsh', HOME: '/home/me' }, claude: '/bin/claude', platform: 'linux' as const, port: 8765, token: 'secret' }

  it('starts Claude Code with the plugin, in the data folder, with the port and token', () => {
    const command = sessionCommand('claude', options)!
    expect(command.file).toBe('/bin/claude')
    expect(command.args).toEqual(['--plugin-dir', join('/data', 'agent-plugin')])
    expect(command.cwd).toBe('/data')
    expect(command.env).toMatchObject({ HOME: '/home/me', KEDAMI_PORT: '8765', KEDAMI_TOKEN: 'secret' })
  })

  it("starts the student's shell, or a default one", () => {
    expect(sessionCommand('shell', options)!.file).toBe('/bin/zsh')
    expect(sessionCommand('shell', { ...options, env: {} })!.file).toBe('/bin/bash')
    expect(sessionCommand('shell', { ...options, env: { COMSPEC: 'C:\\cmd.exe' }, platform: 'win32' })!.file).toBe('C:\\cmd.exe')
  })

  it('has no Claude Code command when it is not installed', () => {
    expect(sessionCommand('claude', { ...options, claude: null })).toBeNull()
  })
})

describe('findOnPath', () => {
  it('finds an executable in the path, in path order, and nothing that is not executable', () => {
    const root = mkdtempSync(join(tmpdir(), 'kedami-path-'))
    const [first, second, plain] = ['a', 'b', 'c'].map((name) => join(root, name))
    for (const dir of [first, second, plain]) mkdirSync(dir)
    for (const dir of [first, second]) {
      writeFileSync(join(dir, 'claude'), '#!/bin/sh\n')
      chmodSync(join(dir, 'claude'), 0o755)
    }
    writeFileSync(join(plain, 'other'), 'not executable')
    expect(findOnPath('claude', `${second}:${first}`, 'linux')).toBe(join(second, 'claude'))
    expect(findOnPath('other', plain, 'linux')).toBeNull()
    expect(findOnPath('claude', '', 'linux')).toBeNull()
  })

  it('tries the Windows executable extensions', () => {
    const root = mkdtempSync(join(tmpdir(), 'kedami-path-'))
    writeFileSync(join(root, 'claude.exe'), '')
    expect(findOnPath('claude', root, 'win32', '.COM;.EXE')).toBe(join(root, 'claude.exe'))
  })
})

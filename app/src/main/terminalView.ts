// The Terminal panel: terminal.html in its own view, laid over the space the lesson window leaves for it.
// The view has its own preload and is the only sender TerminalHub accepts. The lesson window can only show
// or hide it. See architecture/agent-mode.md, Isolation.
import { type BrowserWindow, ipcMain, WebContentsView } from 'electron'
import { join } from 'node:path'
import { spawn } from 'node-pty'
import { findOnPath, isToggleShortcut, type Pty, sessionCommand, TerminalHub } from './terminal'

interface TerminalOptions {
  dataDir: string
  rendererUrl: string | undefined
  port: number
  token: string
}

interface Bounds {
  x: number
  y: number
  width: number
  height: number
}

export function setUpTerminal(window: BrowserWindow, options: TerminalOptions): TerminalHub {
  const view = new WebContentsView({
    webPreferences: {
      preload: join(__dirname, '../preload/terminal.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false
    }
  })
  view.webContents.on('will-navigate', (event) => event.preventDefault())
  view.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  if (options.rendererUrl) {
    view.webContents.loadURL(`${options.rendererUrl}/terminal.html`)
  } else {
    view.webContents.loadFile(join(__dirname, '../renderer/terminal.html'))
  }

  const hub = new TerminalHub({
    isTerminal: (sender) => sender === view.webContents,
    command: (kind) =>
      sessionCommand(kind, {
        dataDir: options.dataDir,
        env: process.env,
        // Looked up each time, so installing Claude Code while the app is open is enough.
        claude: findOnPath('claude', process.env.PATH ?? '', process.platform, process.env.PATHEXT),
        platform: process.platform,
        port: options.port,
        token: options.token
      }),
    spawn: (command, cols, rows): Pty => {
      const pty = spawn(command.file, command.args, {
        name: 'xterm-256color',
        cols,
        rows,
        cwd: command.cwd,
        env: command.env
      })
      return {
        write: (data) => pty.write(data),
        resize: (c, r) => pty.resize(c, r),
        kill: () => pty.kill(),
        onData: (listener) => void pty.onData(listener),
        onExit: (listener) => void pty.onExit(({ exitCode }) => listener(exitCode))
      }
    },
    send: (channel, value) => {
      if (!view.webContents.isDestroyed()) view.webContents.send(channel, value)
    }
  })

  ipcMain.handle('terminal:state', (event) => hub.state(event.sender))
  ipcMain.handle('terminal:start', (event, kind, cols, rows) => hub.start(event.sender, kind, cols, rows))
  ipcMain.on('terminal:input', (event, data) => hub.input(event.sender, data))
  ipcMain.on('terminal:resize', (event, cols, rows) => hub.resize(event.sender, cols, rows))

  // The panel shortcut works wherever the keyboard is, the terminal included; the lesson window decides what it does.
  const toggle = (event: Electron.Event, input: Electron.Input) => {
    if (!isToggleShortcut(input, process.platform)) return
    event.preventDefault()
    window.webContents.send('kedami:terminal-toggle')
  }
  window.webContents.on('before-input-event', toggle)
  view.webContents.on('before-input-event', toggle)

  // From the lesson window: where to show the view, and when to hide it. A hidden session keeps running.
  const fromWindow = (sender: unknown) => sender === window.webContents
  ipcMain.on('kedami:terminal-show', (event, bounds: unknown) => {
    if (!fromWindow(event.sender) || !isBounds(bounds)) return
    window.contentView.addChildView(view)
    view.setBounds(bounds)
  })
  ipcMain.on('kedami:terminal-hide', (event) => {
    if (!fromWindow(event.sender)) return
    window.contentView.removeChildView(view)
  })
  return hub
}

function isBounds(value: unknown): value is Bounds {
  if (typeof value !== 'object' || value === null) return false
  const { x, y, width, height } = value as Record<string, unknown>
  return [x, y, width, height].every((n) => Number.isInteger(n) && (n as number) >= 0 && (n as number) <= 100_000)
}

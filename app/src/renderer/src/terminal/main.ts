// The Terminal panel's page: the session drawn with xterm.js. Shown with no session running, it starts Claude Code,
// or the student's shell if Claude Code isn't installed. It talks only to its own preload, and links in the output
// don't open. See architecture/agent-mode.md, Terminal panel.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/jetbrains-mono/400.css'
import '@xterm/xterm/css/xterm.css'
import '../styles/tokens.css'
import '../styles/base.css'
import './terminal.css'

import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import type { SessionKind } from '../../../preload/terminal-api'

const root = document.getElementById('terminal-root')!
const token = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()

const start = document.createElement('div')
start.className = 'terminal-start'
const screen = document.createElement('div')
screen.className = 'terminal-screen'
const fitHost = document.createElement('div')
fitHost.className = 'terminal-fit'
screen.append(fitHost)
root.append(start, screen)

const term = new Terminal({
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: 14,
  cursorBlink: true,
  theme: {
    background: token('bg'),
    foreground: token('text'),
    cursor: token('text'),
    selectionBackground: token('surface-raised')
  }
})
const fit = new FitAddon()
term.loadAddon(fit)
term.open(fitHost)
term.onData((data) => window.terminal.input(data))
term.onResize(({ cols, rows }) => window.terminal.resize(cols, rows))
window.terminal.onData((data) => term.write(data))
// Shown in the terminal itself before a plain shell starts. Plain text: the app opens no links.
const NOT_INSTALLED =
  "Claude Code isn't installed, so this is a plain shell. Install it from code.claude.com, then exit this shell " +
  'and open the panel again.'

let running = false
let starting = false
// Which session the last start ran, for the button that starts it again.
let lastKind: SessionKind = 'claude'

window.terminal.onExit((code) => showEnded(code))
window.terminal.onShown(() => {
  if (!running) startSession()
})
new ResizeObserver(() => {
  if (!screen.hidden) fit.fit()
}).observe(root)

/** Start Claude Code, or the shell if Claude Code isn't installed, unless a session is already running. */
async function startSession(): Promise<void> {
  if (starting) return
  starting = true
  try {
    const state = await window.terminal.state()
    if (state.running) {
      running = true
      return showSession()
    }
    lastKind = state.claude ? 'claude' : 'shell'
    term.reset()
    if (!state.claude) term.write(`\x1b[2m${NOT_INSTALLED}\x1b[0m\r\n\r\n`)
    start.hidden = true
    screen.hidden = false
    fit.fit()
    const started = await window.terminal.start(lastKind, term.cols, term.rows)
    running = started.running !== null
    if (running) showSession()
    else showEnded(null)
  } finally {
    starting = false
  }
}

function showSession(): void {
  start.hidden = true
  screen.hidden = false
  fit.fit()
  term.focus()
}

/** After a session exits: its exit code, and a button to start one again. */
function showEnded(exitCode: number | null): void {
  running = false
  screen.hidden = true
  start.hidden = false
  const ended = paragraph(
    exitCode === null ? "The session couldn't start." : `The session ended with exit code ${exitCode}.`
  )
  const again = document.createElement('button')
  again.type = 'button'
  again.className = 'button button-primary'
  again.textContent = lastKind === 'claude' ? 'Start Claude Code' : 'Open a shell'
  again.addEventListener('click', () => startSession())
  start.replaceChildren(ended, again)
}

function paragraph(text: string): HTMLParagraphElement {
  const element = document.createElement('p')
  element.className = 'muted'
  element.textContent = text
  return element
}

// Nothing shows until the panel is first opened.
start.hidden = true
screen.hidden = true

// The Terminal screen's page: buttons to start a session, then the session drawn with xterm.js. It talks
// only to its own preload, and links in the output don't open. See architecture/agent-mode.md, Terminal screen.
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
term.open(screen)
term.onData((data) => window.terminal.input(data))
term.onResize(({ cols, rows }) => window.terminal.resize(cols, rows))
window.terminal.onData((data) => term.write(data))
window.terminal.onExit((code) => showStart(code))
new ResizeObserver(() => {
  if (!screen.hidden) fit.fit()
}).observe(root)

function showSession(): void {
  start.hidden = true
  screen.hidden = false
  fit.fit()
  term.focus()
}

async function showStart(exitCode: number | null = null): Promise<void> {
  const { running, claude } = await window.terminal.state()
  if (running) return showSession()
  screen.hidden = true
  start.hidden = false
  start.replaceChildren()

  const heading = document.createElement('h1')
  heading.textContent = 'Terminal'
  const about = paragraph(
    "Claude Code runs here on your own Claude login, with Kedami's plugin. Run /kedami:lesson to build a lesson " +
      'waiting for Claude Code.'
  )
  const buttons = document.createElement('div')
  buttons.className = 'terminal-buttons'
  buttons.append(button('Start Claude Code', 'claude', !claude, true), button('Open a shell', 'shell', false, false))
  start.append(heading, about, buttons)
  if (!claude) {
    // Plain text: the app opens no links but LeetCode's and pgexercises'.
    start.append(paragraph("Claude Code isn't installed. Install it from code.claude.com, then open the Terminal again."))
  }
  if (exitCode !== null) start.append(paragraph(`The last session ended with exit code ${exitCode}.`))
}

function button(label: string, kind: SessionKind, disabled: boolean, primary: boolean): HTMLButtonElement {
  const element = document.createElement('button')
  element.type = 'button'
  element.className = primary ? 'button button-primary' : 'button'
  element.textContent = label
  element.disabled = disabled
  element.addEventListener('click', async () => {
    term.reset()
    screen.hidden = false
    fit.fit()
    const { running } = await window.terminal.start(kind, term.cols, term.rows)
    if (running) showSession()
    else showStart()
  })
  return element
}

function paragraph(text: string): HTMLParagraphElement {
  const element = document.createElement('p')
  element.className = 'muted'
  element.textContent = text
  return element
}

showStart()

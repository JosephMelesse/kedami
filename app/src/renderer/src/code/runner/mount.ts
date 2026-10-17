// Mounts the code runner's sandboxed frame, hidden, and connects a runner to it.

import { type CodeRunner, createRunner, type FramePort } from './client'

export function mountRunner(container: HTMLElement): CodeRunner {
  const iframe = document.createElement('iframe')
  iframe.src = 'runner.html'
  iframe.sandbox.add('allow-scripts')
  iframe.referrerPolicy = 'no-referrer'
  iframe.title = 'Code runner'
  iframe.hidden = true
  container.appendChild(iframe)

  const port: FramePort = {
    post: (message, transfer = []) => iframe.contentWindow?.postMessage(message, '*', transfer),
    listen: (handler) => {
      const listener = (event: MessageEvent): void => {
        if (event.source === iframe.contentWindow) handler(event.data)
      }
      window.addEventListener('message', listener)
      return () => window.removeEventListener('message', listener)
    }
  }
  const runner = createRunner(port, {
    // A separate chunk, so lessons without code problems never load Pyodide's script.
    frameSource: () => import('./frameEntry.ts?bundle').then((module) => module.default),
    files: () => window.kedami.runnerFiles()
  })
  return {
    ready: runner.ready,
    run: runner.run,
    dispose: () => {
      runner.dispose()
      iframe.remove()
    }
  }
}

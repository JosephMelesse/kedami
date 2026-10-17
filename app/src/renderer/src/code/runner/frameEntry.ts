// The script the runner frame runs, bundled with the worker's source. runner.html evaluates it and
// calls `start`. See architecture/code-problems.md, Runner.

import { createFrame } from './frame'
import type { FromFrame, RuntimeFiles } from './protocol'
import workerSource from './worker.ts?bundle=es'
import type { RunRequest } from '../harness'

export function start(
  files: RuntimeFiles,
  send: (message: FromFrame) => void
): (id: number, request: RunRequest) => void {
  // The frame has no origin, so the worker can't be loaded from a file. Chromium also refuses a blob URL
  // made in a frame with no origin, so the worker starts from a data URL of its source.
  const url = `data:text/javascript;base64,${base64(new TextEncoder().encode(workerSource))}`
  const frame = createFrame(files, {
    send,
    createWorker: (onMessage, onError) => {
      const worker = new Worker(url, { type: 'module' })
      worker.onmessage = (event) => onMessage(event.data)
      worker.onerror = (event) => onError(event.message)
      return worker
    },
    setTimer: (callback, ms) => setTimeout(callback, ms),
    clearTimer: (timer) => clearTimeout(timer as ReturnType<typeof setTimeout>)
  })
  return (id, request) => frame.run(id, request)
}

function base64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}

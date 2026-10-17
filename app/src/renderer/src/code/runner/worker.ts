// The worker inside the runner frame: loads Pyodide and runs requests through the harness.
// It is bundled whole, Pyodide included, since nothing can be loaded from a URL here: the frame hands it
// Pyodide's binaries, and fetch is answered from them. See architecture/code-problems.md, Runner.

import { loadPyodide } from 'pyodide'
import createPyodideModule from 'pyodide/pyodide.asm.mjs'
import lockFile from 'pyodide/pyodide-lock.json?raw'
import { type Harness, loadHarness } from '../harness'
import type { FromWorker, RuntimeFiles, ToWorker } from './protocol'

// Pyodide asks for its files by URL under this base; none of them reaches the network.
const BASE = 'https://pyodide.invalid/'

const send = (message: FromWorker): void => postMessage(message)
let harness: Harness | null = null

async function start(files: RuntimeFiles): Promise<void> {
  const served: Record<string, { body: ArrayBuffer; type: string }> = {
    [`${BASE}pyodide.asm.wasm`]: { body: files.wasm, type: 'application/wasm' },
    [`${BASE}python_stdlib.zip`]: { body: files.stdlib, type: 'application/zip' }
  }
  globalThis.fetch = async (input: RequestInfo | URL) => {
    const file = served[String(input instanceof Request ? input.url : input)]
    if (!file) throw new TypeError('The runner has no network.')
    return new Response(file.body.slice(0), { headers: { 'Content-Type': file.type } })
  }
  const pyodide = await loadPyodide({
    indexURL: BASE,
    createPyodideModule,
    lockFileContents: lockFile,
    stdout: () => {},
    stderr: () => {}
  })
  harness = loadHarness(pyodide)
}

onmessage = (event: MessageEvent<ToWorker>) => {
  const message = event.data
  if (message.type === 'start') {
    start(message.files).then(
      () => send({ type: 'ready' }),
      (error) => send({ type: 'failed', message: String((error && error.message) || error) })
    )
  } else if (message.type === 'run' && harness) {
    const { id, request } = message
    const result = harness(request, (r) => send({ type: 'result', id, result: r }))
    send({ type: 'done', id, result })
  }
}

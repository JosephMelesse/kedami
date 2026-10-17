// Pyodide's binaries for the code runner. Its frame has no origin and can't load files, so the renderer
// asks main for them and hands them on. Only these two files, from the installed package, are read.
import { readFile } from 'node:fs/promises'

const FILES = { wasm: 'pyodide/pyodide.asm.wasm', stdlib: 'pyodide/python_stdlib.zip' } as const

let files: Promise<{ wasm: ArrayBuffer; stdlib: ArrayBuffer }> | null = null

async function read(name: string): Promise<ArrayBuffer> {
  const data = await readFile(require.resolve(name))
  return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) as ArrayBuffer
}

/** Read once per app session; a failed read is retried on the next request. */
export function readRunnerFiles(): Promise<{ wasm: ArrayBuffer; stdlib: ArrayBuffer }> {
  files ??= Promise.all([read(FILES.wasm), read(FILES.stdlib)]).then(([wasm, stdlib]) => ({ wasm, stdlib }))
  files.catch(() => (files = null))
  return files
}

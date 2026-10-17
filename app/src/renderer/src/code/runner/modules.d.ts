// Scripts bundled whole by scripts/bundle-plugin.ts, imported as their source.
declare module '*?bundle' {
  const source: string
  export default source
}

declare module '*?bundle=es' {
  const source: string
  export default source
}

// Pyodide's Emscripten module, passed to loadPyodide so the worker needs no dynamic import.
declare module 'pyodide/pyodide.asm.mjs' {
  const createPyodideModule: NonNullable<import('pyodide').PyodideConfig['createPyodideModule']>
  export default createPyodideModule
}

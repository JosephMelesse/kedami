// Imports a module as the source text of one self-contained script: `./frame.ts?bundle` for a classic
// script, `./worker.ts?bundle=es` for a module worker. The code runner needs this because its frame has
// no origin, so it can't load scripts or workers from URLs; it is handed their source instead.
import { build, type Plugin } from 'vite'

const BUNDLE = /\?bundle(=es)?$/

// Library mode inlines every file named by `new URL(file, import.meta.url)` as a data URL. Pyodide names
// its 9.6 MB wasm that way as a fallback it never uses here, since the runner is handed its binaries.
const keepFileUrls: Plugin = {
  name: 'kedami-bundle-keep-file-urls',
  enforce: 'pre',
  transform(code) {
    if (!code.includes('import.meta.url')) return null
    return code.replace(/new URL\((["'][^"']+["']),\s*import\.meta\.url\)/g, 'new URL($1, self.location.href)')
  }
}

export function bundlePlugin(): Plugin {
  return {
    name: 'kedami-bundle',
    enforce: 'pre',
    async resolveId(source, importer) {
      const match = BUNDLE.exec(source)
      if (!match) return null
      const resolved = await this.resolve(source.slice(0, match.index), importer, { skipSelf: true })
      return resolved && resolved.id + match[0]
    },
    async load(id) {
      const match = BUNDLE.exec(id)
      if (!match) return null
      const entry = id.slice(0, match.index)
      const format = match[1] ? 'es' : 'iife'
      const result = await build({
        configFile: false,
        logLevel: 'warn',
        plugins: [bundlePlugin(), keepFileUrls],
        assetsInclude: ['**/*.whl'],
        build: {
          write: false,
          emptyOutDir: false,
          lib: { entry, formats: [format], name: 'Bundle', fileName: 'bundle' },
          rollupOptions: {
            // Pyodide's Node-only branches import these; they never run in a browser.
            external: [/^node:/, 'ws'],
            output: { inlineDynamicImports: true },
            // Pyodide uses eval by design; it runs in the sandboxed frame, whose CSP allows it.
            onwarn(warning, warn) {
              if (warning.code !== 'EVAL' || !warning.id?.includes('pyodide')) warn(warning)
            }
          }
        }
      })
      const outputs = Array.isArray(result) ? result : [result]
      const chunk = outputs.flatMap((o) => ('output' in o ? o.output : [])).find((o) => o.type === 'chunk')
      if (!chunk) throw new Error(`bundling ${entry} produced no script`)
      for (const module of Object.keys(chunk.modules)) {
        if (!module.startsWith('\0')) this.addWatchFile(module.replace(/\?.*$/, ''))
      }
      return `export default ${JSON.stringify(chunk.code)}`
    }
  }
}

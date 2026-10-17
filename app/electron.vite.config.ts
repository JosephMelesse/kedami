import react from '@vitejs/plugin-react'
import { defineConfig } from 'electron-vite'
import { resolve } from 'node:path'
import { bundlePlugin } from './scripts/bundle-plugin'

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    plugins: [react(), bundlePlugin()],
    // The code runner's vendored Python package; see src/renderer/src/code/harness.ts.
    assetsInclude: ['**/*.whl'],
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/renderer/index.html'),
          // The sandboxed page simulations run in.
          simulation: resolve(__dirname, 'src/renderer/simulation.html'),
          // The sandboxed page the student's code runs in.
          runner: resolve(__dirname, 'src/renderer/runner.html')
        }
      }
    }
  }
})

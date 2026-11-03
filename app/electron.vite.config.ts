import react from '@vitejs/plugin-react'
import { defineConfig } from 'electron-vite'
import { resolve } from 'node:path'

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    plugins: [react()],
    // The dev server's port. Main reads the address Vite actually uses, so a taken port only moves it.
    server: { port: 5000 },
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/renderer/index.html'),
          // The sandboxed page simulations run in.
          simulation: resolve(__dirname, 'src/renderer/simulation.html')
        }
      }
    }
  }
})

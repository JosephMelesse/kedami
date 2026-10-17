import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // The code runner's vendored Python package; see src/renderer/src/code/harness.ts.
  assetsInclude: ['**/*.whl'],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}', 'tests/**/*.test.ts'],
    css: false
  }
})

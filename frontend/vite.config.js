import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // Node stays the default so the pure-module suites (grounds, recall,
    // perceptMentions, blockConvert, visionActivity, circulationThread) run
    // exactly as they did before this config existed — same speed, no DOM.
    //
    // A DOM is expensive and almost never what these tests need: the project's
    // discipline is that behaviour lives in pure modules and components render
    // them. Files that genuinely must mount something opt in BY NAME with
    // `*.dom.test.jsx`, which keeps the cost where it is earned and makes the
    // choice visible in the filename rather than buried in config.
    environment: 'node',
    environmentMatchGlobs: [['**/*.dom.test.jsx', 'jsdom']],
    globals: true,
    setupFiles: ['./src/test/setup.dom.js'],
  },
})

import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import svgr from 'vite-plugin-svgr'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // svgr BEFORE react so the JSX it emits is handed to @vitejs/plugin-react.
    //
    // `include` is confined to the migrated landing assets (glyphs + diagrams)
    // so svgr claims ONLY those svgs; the app's brand marks and any other svg
    // stay ordinary vite URL assets. `exportType: 'named'` makes each glyph a
    // named `ReactComponent` export, importable straight from its plain path:
    //   import { ReactComponent as Differential } from '@/assets/glyphs/07-differential.svg'
    //
    // vite-plugin-svgr v5's `load` hook REPLACES the module, so it cannot also
    // emit a default URL from that same plain path (an architectural either/or,
    // unlike the old CRA dual export). The URL mode therefore uses vite's own
    // `?url` query, which svgr's include does not match and so leaves alone:
    //   import atlasUrl from '@/assets/glyphs/09-atlas.svg?url'
    //
    // SVGO is OPT-IN in vite-plugin-svgr (it only runs if you add
    // '@svgr/plugin-svgo'), so leaving it out means the SVG is NOT rewritten:
    // root `id` attributes, per-glyph scoped `<style>` blocks and every path
    // coordinate survive byte-for-byte. That is the whole contract — twenty-one
    // id-scoped glyphs coexist in one document only because their ids and styles
    // are untouched.
    svgr({
      include: ['**/src/assets/glyphs/**/*.svg', '**/src/assets/diagrams/**/*.svg'],
      svgrOptions: {
        exportType: 'named',
        namedExport: 'ReactComponent',
      },
    }),
    react(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
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

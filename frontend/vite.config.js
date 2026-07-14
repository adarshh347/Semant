import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Split the heavy editor vendors into their own chunks. These are only
        // imported by the lazy editor routes (BlockNote/TipTap), so they stay
        // off the initial load; splitting them keeps any single chunk under the
        // 500 kB warning threshold instead of one ~960 kB "style" blob.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('@mantine')) return 'vendor-mantine'
          if (id.includes('@blocknote')) return 'vendor-blocknote'
          if (
            id.includes('/yjs/') ||
            id.includes('y-protocols') ||
            id.includes('/lib0/')
          ) return 'vendor-yjs'
          if (
            id.includes('prosemirror') ||
            id.includes('@tiptap')
          ) return 'vendor-prosemirror'
          if (
            id.includes('/react/') ||
            id.includes('/react-dom/') ||
            id.includes('/scheduler/')
          ) return 'vendor-react'
          return undefined
        },
      },
    },
  },
})

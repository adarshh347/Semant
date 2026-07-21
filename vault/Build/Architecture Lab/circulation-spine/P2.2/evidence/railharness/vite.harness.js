import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// P2.2 fixture-harness build (NOT production). Builds railharness/ → railharness-dist/ with no
// file watching, so it survives the ENOSPC inotify limit that blocks `vite dev` here.
export default defineConfig({
  plugins: [react()],
  root: 'railharness',
  build: { outDir: '../railharness-dist', emptyOutDir: true },
});

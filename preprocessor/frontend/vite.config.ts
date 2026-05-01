import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const chunkMap: Record<string, string[]> = {
  'antd-vendor': ['antd'],
  'pdf-worker': ['pdfjs-dist'],
  'react-vendor': ['react', 'react-dom'],
  'dnd-kit': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
}

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          for (const [chunk, pkgs] of Object.entries(chunkMap)) {
            if (pkgs.some((pkg) => id.includes(`/node_modules/${pkg}/`))) {
              return chunk
            }
          }
        },
      },
    },
    chunkSizeWarningLimit: 2000,
  },
  optimizeDeps: {
    include: ['pdfjs-dist', 'antd'],
  },
})

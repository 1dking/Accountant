import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    // OBrainAdapter calls /api/platform-admin/events/* — proxy to the real
    // backend dev server so the Lab can run against live data without CORS
    // setup. See .env.example for the admin token this needs.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})

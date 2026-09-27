import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: ['proxpc', 'proxpc.local', '.ts.net', 'localhost'],
    // Same-origin /api fallback still goes to Tailscale hostname
    proxy: {
      '/api': 'http://proxpc:8000',
      '/health': 'http://proxpc:8000',
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_API_URL se inyecta por docker-compose como variable de entorno.
// v1: http://backend:8000   v2: http://backend_v2:8000
const backendTarget = process.env.VITE_API_URL || 'http://backend:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})

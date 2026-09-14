import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const BACKEND_URL = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/tasks': BACKEND_URL,
      '/chat': BACKEND_URL,
      '/reminders': BACKEND_URL,
      '/health': BACKEND_URL,
      '/conversations': BACKEND_URL,
    },
  },
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
})

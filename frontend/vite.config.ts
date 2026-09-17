import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 显式 127.0.0.1：避免只监听 ::1 导致 proxy 目标 localhost 不可达
    host: '127.0.0.1',
    port: 7301,
    strictPort: true,
    proxy: {
      // /events 为后续 SSE 预留，本期后端无此路由（404 是预期）
      '/api': 'http://localhost:7302',
      '/events': 'http://localhost:7302',
    },
  },
})

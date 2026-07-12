import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // 对 SSE 流式请求禁用缓冲
            if (req.url?.includes('stream') || req.url?.includes('generate-message')) {
              proxyReq.setHeader('Accept', 'text/event-stream');
            }
          });
        },
      },
    },
  },
})

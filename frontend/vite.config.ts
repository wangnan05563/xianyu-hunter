import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  // SPA 挂载在 /app/ 路径下，构建产物资源路径需以 /app/ 为前缀
  base: '/app/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // 开发模式代理 API 到 FastAPI 后端
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../src/xianyu_hunter/web/static/spa',
    emptyOutDir: true,
    // 拆分大依赖，降低首屏体积
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'antd-vendor': ['antd', '@ant-design/icons'],
          // echarts-for-react 已替换为按需导入的 echarts/core 封装组件，不再需要单独列出
          'echarts-vendor': ['echarts'],
          'dnd-vendor': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
        },
      },
    },
  },
})

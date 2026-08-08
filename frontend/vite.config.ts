import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    // O-12-26 PWA 移动端优化：让 SPA 可被"添加到主屏幕"并支持离线访问
    // 关键设计：
    // 1. manifest 跟随 base('/xianyu/')，scope/start_url 自动指向 /xianyu/
    // 2. workbox 预缓存静态资源 + 运行时缓存只读 GET 接口
    // 3. SSE (/api/events/stream) 和鉴权 (/api/auth/*) 必须排除，避免长连接被 SW 拦截或登录态串号
    VitePWA({
      // autoUpdate：新 SW 就绪即自动 skipWaiting 激活，下次刷新即拿到新版本
      // 为什么不用 'prompt'：prompt 模式下新 SW 进入 waiting 状态，
      // 当旧 SW 缓存的旧 index.html 引用已删除的 JS chunk 时，SPA 启动失败，
      // ReloadPrompt 组件根本无法 mount 显示更新通知，导致用户被永久卡在白屏/路由不跳转
      // （此问题已在 2026-07-08 与 2026-07-09 两次复现，故改用 autoUpdate 彻底根治）
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'favicon-32x32.png', 'favicon-48x48.png', 'apple-touch-icon.png'],
      manifest: {
        name: '闲鱼猎人 XianyuHunter',
        short_name: '闲鱼猎人',
        description: '闲鱼商品智能监控、自动评估与抢单工具',
        theme_color: '#FF6200',
        background_color: '#FFFFFF',
        display: 'standalone',
        orientation: 'portrait-primary',
        // scope 与 start_url 不写，让 vite-plugin-pwa 自动用 base 派生为 /xianyu/
        lang: 'zh-CN',
        start_url: '/xianyu/',
        scope: '/xianyu/',
        icons: [
          // SVG 矢量图标：Chrome/Edge/Android 支持，任意尺寸自适应
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          // maskable：Android 自适应遮罩，关键内容需在安全区 (中间 80%)
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'maskable' },
          // iOS 不支持 SVG，回退到现有 PNG（apple-touch-icon 通常 180x180）
          { src: 'apple-touch-icon.png', sizes: '180x180', type: 'image/png', purpose: 'any' },
        ],
      },
      workbox: {
        // 预缓存构建产物 + public 静态资源
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024, // 4MB，容纳 echarts/antd 大 chunk
        navigateFallback: 'index.html', // SPA 路由回退
        // API 请求不走 SPA 回退（同时覆盖根路径 /api/ 与子路径部署命名空间 /xianyu/api/）
        navigateFallbackDenylist: [/^\/api\//, /^\/xianyu\/api\//],
        runtimeCaching: [
          {
            // 静态图片资源：长期缓存
            urlPattern: ({ url }) => url.pathname.endsWith('.png') || url.pathname.endsWith('.jpg') || url.pathname.endsWith('.jpeg') || url.pathname.endsWith('.webp'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'xh-img-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 3600 },
            },
          },
          {
            // 只读 GET 接口：NetworkFirst，断网时回退缓存
            // 关键排除项：
            //  - /api/events/stream: SSE 长连接，被 SW 拦截会让 EventSource 卡住
            //  - /api/auth/*: 鉴权接口，缓存会串号或污染登录态
            //  - /api/export/*: 流式响应，缓存会破坏分块下载
            // 子路径部署下接口前缀为 /xianyu/api/，需同步覆盖
            urlPattern: ({ url, request }) => {
              const p = url.pathname
              const isApi = p.startsWith('/api/') || p.startsWith('/xianyu/api/')
              return (
                request.method === 'GET'
                && isApi
                && !p.startsWith('/api/events/stream')
                && !p.startsWith('/xianyu/api/events/stream')
                && !p.startsWith('/api/auth/')
                && !p.startsWith('/xianyu/api/auth/')
                && !p.startsWith('/api/export/')
                && !p.startsWith('/xianyu/api/export/')
              )
            },
            handler: 'NetworkFirst',
            options: {
              cacheName: 'xh-api-cache',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 200, maxAgeSeconds: 5 * 60 },
              matchOptions: { ignoreVary: true },
            },
          },
        ],
      },
      devOptions: {
        enabled: false, // 开发模式不启用 SW，避免热更新被缓存干扰
      },
    }),
  ],
  // SPA 挂载在 /xianyu/ 路径下，构建产物资源路径需以 /xianyu/ 为前缀
  base: '/xianyu/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // 开发模式代理 API 到 FastAPI 后端
    proxy: {
      '/xianyu/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/xianyu/, ''),
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

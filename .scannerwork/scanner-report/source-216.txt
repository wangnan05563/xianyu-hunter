import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { ThemeProvider, useTheme } from './contexts/ThemeContext'
import './index.css'

// 主题令牌：干净明亮的扁平化设计语言
// 设计原则：
// 1. 主色采用闲鱼品牌橙（#FF6200），呼应业务场景并区别于 antd 默认蓝
// 2. 圆角统一 8px，现代感且不过于圆润
// 3. 阴影克制，仅 hover 时强化，避免视觉噪音
// 4. 字体栈优先系统字体，保证渲染性能
const baseTheme = {
  token: {
    colorPrimary: '#FF6200',
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#ff4d4f',
    colorInfo: '#1677ff',
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    fontSize: 14,
    controlHeight: 36,
    controlHeightLG: 44,
    boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
    boxShadowSecondary: '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
  },
  components: {
    Card: {
      paddingLG: 20,
      headerHeight: 56,
      headerFontSize: 15,
    },
    Menu: {
      itemHeight: 44,
      iconSize: 16,
      activeBarBorderWidth: 0,
    },
    Statistic: {
      titleFontSize: 13,
      contentFontSize: 28,
    },
    Table: {
      headerBg: '#fafafa',
      headerColor: '#262626',
      rowHoverBg: '#fff7f0',
    },
    Button: {
      primaryShadow: 'none',
      defaultShadow: 'none',
    },
  },
}

// 顶层 ConfigProvider 包装：根据主题应用 algorithm
// 关键修复：之前 main.tsx 的 ConfigProvider 没有 algorithm，
// 导致 Login 页（独立路由，不在 MainLayout 内）永远使用默认浅色主题。
// 现在让顶层 ConfigProvider 也响应 useTheme，让所有路由都能切换主题。
function ThemedRoot() {
  const { isDark } = useTheme()
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        ...baseTheme,
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        components: {
          ...baseTheme.components,
          Table: {
            ...baseTheme.components.Table,
            // 暗色主题下：baseTheme 的 rowHoverBg '#fff7f0' 是接近白色的淡橙，
            // 与暗色文字 rgba(255,255,255,0.88)≈#e0e0e0 对比度极低，hover 时文字几乎看不见。
            // 改用品牌色淡橙透明叠加：与卡片背景 #1f1f1f 形成明显对比、文字仍清晰可读，
            // 同时与浅色主题 #fff7f0 淡橙 hover 风格保持一致。
            // darkAlgorithm 不会重算显式指定的 token，故必须在此处动态覆盖。
            rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0',
          },
        },
      }}
    >
      <BrowserRouter basename="/app">
        <App />
      </BrowserRouter>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <ThemedRoot />
    </ThemeProvider>
  </React.StrictMode>,
)

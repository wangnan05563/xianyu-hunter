import { Outlet } from 'react-router-dom'
import { theme } from 'antd'
import MobileHeader from './MobileHeader'
import TabBar from '../components/TabBar'
import OfflineBanner from '../components/OfflineBanner'
// 移动端全局样式：TabBar / Header / TaskCard / Markdown 渲染样式
// 在 main.tsx 引入会污染桌面端布局，必须仅在移动端 Layout 引入
import '../styles/mobile.css'

// 移动端主布局：Header + Content + TabBar
export default function MobileLayout() {
  const { token: themeToken } = theme.useToken()

  return (
    <div
      className="m-layout"
      style={{
        background: themeToken.colorBgLayout,
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <MobileHeader />
      <OfflineBanner />
      <main
        id="m-content"
        className="m-content"
        style={{ flex: 1, overflow: 'auto', paddingBottom: 56 }}
      >
        <Outlet />
      </main>
      <TabBar />
    </div>
  )
}

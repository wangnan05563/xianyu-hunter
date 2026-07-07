import { useState, useEffect } from 'react'
import { WifiOutlined } from '@ant-design/icons'

// 离线横幅：监听 online/offline 事件，断网时顶部显示提示
export default function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(navigator.onLine)

  useEffect(() => {
    const goOnline = () => setIsOnline(true)
    const goOffline = () => setIsOnline(false)
    globalThis.addEventListener('online', goOnline)
    globalThis.addEventListener('offline', goOffline)
    return () => {
      globalThis.removeEventListener('online', goOnline)
      globalThis.removeEventListener('offline', goOffline)
    }
  }, [])

  if (isOnline) return null

  // S6819: 改用 <output> 替代 role="status"，原生具备 live region 语义
  return (
    <output
      aria-live="polite"
      style={{
        background: '#D4A017',
        color: '#fff',
        textAlign: 'center',
        padding: '6px 16px',
        fontSize: 13,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
      }}
    >
      <WifiOutlined />
      网络已断开，正在显示缓存数据
    </output>
  )
}


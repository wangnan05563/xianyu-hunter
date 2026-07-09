import { useEffect, useState } from 'react'
import { App, Button, Space, Typography } from 'antd'

const { Text } = Typography

/**
 * O-12-26 PWA 状态提示组件
 *
 * 配套 vite.config.ts 的 registerType: 'autoUpdate'：
 * 新 SW 就绪即自动 skipWaiting 激活，无需用户干预即可拿到新版本。
 * 本组件仅保留 onOfflineReady 通知（应用首次可离线使用时提示一次），
 * onNeedRefresh 分支在 autoUpdate 模式下不会被调用，但保留兼容代码
 * 以便未来切回 'prompt' 模式时无需重写。
 *
 * 使用 antd App.useApp() 获取上下文 notification 实例，
 * 确保主题令牌（深浅色）能在通知中正确生效。
 */
export default function ReloadPrompt() {
  const { notification } = App.useApp()
  const [needRefresh, setNeedRefresh] = useState(false)
  const [offlineReady, setOfflineReady] = useState(false)
  // registerSW 返回的 update 函数：调用后触发 SW skipWaiting 并按需重载页面
  const [updateSw, setUpdateSw] = useState<((reloadPage?: boolean) => Promise<void>) | null>(null)

  useEffect(() => {
    // 生产构建后才存在 virtual:pwa-register 模块，开发模式 vite 会跳过此 import
    import('virtual:pwa-register').then(({ registerSW }) => {
      const update = registerSW({
        onNeedRefresh() {
          setNeedRefresh(true)
        },
        onOfflineReady() {
          setOfflineReady(true)
        },
      })
      // 用函数式更新避免 React 把 update 当作 updater 调用（update 本身是函数）
      setUpdateSw(() => update)
    }).catch(() => {
      // 开发模式或 PWA 关闭时，virtual 模块不存在，静默忽略
    })
  }, [])

  useEffect(() => {
    if (!needRefresh) return
    const key = `pwa-update-${Date.now()}`
    notification.open({
      key,
      message: '新版本可用',
      description: '检测到应用有新版本，刷新页面以加载最新功能。',
      duration: 0, // 不自动关闭，避免用户错过
      btn: (
        <Space>
          <Button size="small" onClick={() => notification.destroy(key)}>
            稍后
          </Button>
          <Button
            type="primary"
            size="small"
            onClick={() => {
              notification.destroy(key)
              if (updateSw) {
                void updateSw(true) // skipWaiting + 重载页面
              } else {
                globalThis.location.reload()
              }
            }}
          >
            立即刷新
          </Button>
        </Space>
      ),
    })
  }, [needRefresh, notification, updateSw])

  useEffect(() => {
    if (!offlineReady) return
    const key = `pwa-offline-${Date.now()}`
    notification.open({
      key,
      message: '应用已可离线使用',
      description: (
        <Text type="secondary">
          静态资源与近期 API 响应已缓存，断网时仍可查看已加载过的页面。
        </Text>
      ),
      duration: 4,
      btn: (
        <Button size="small" onClick={() => notification.destroy(key)}>
          知道了
        </Button>
      ),
    })
  }, [offlineReady, notification])

  // 该组件本身不渲染可见 DOM，仅通过 antd notification 通知
  return null
}

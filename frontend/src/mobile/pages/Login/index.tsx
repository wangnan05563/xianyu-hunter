// frontend/src/mobile/pages/Login/index.tsx
import { Card, Button, Spin, Input, App, Tag, Space } from 'antd'
import { useEffect, useState, useCallback } from 'react'
import { authApi } from '../../../api'
import type { CookieInjectResult, BrowserImportStatus } from '../../../api/auth'
import { extractApiError } from '../../../utils/apiError'

// 处理导入结果统一返回的成功/失败提示
// 为什么提取：浏览器导入与 Cookie 注入返回结构一致，复用同一逻辑
function getResultError(result: CookieInjectResult): string | undefined {
  return result.error || result.hint
}

export default function MobileLogin() {
  const { message } = App.useApp()
  const [browserStatus, setBrowserStatus] = useState<BrowserImportStatus | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [importing, setImporting] = useState(false)
  const [cookieText, setCookieText] = useState('')

  // 首次加载拉取浏览器状态：决定哪些导入按钮可见/可用
  const fetchBrowserStatus = useCallback(async () => {
    setLoadingStatus(true)
    try {
      const data = await authApi.getBrowserImportStatus()
      setBrowserStatus(data)
    } catch (e) {
      // 静默失败：状态展示位可留空，不阻断用户操作；仅打 warn 便于排查
      console.warn(extractApiError(e, '获取浏览器导入状态失败'))
    } finally {
      setLoadingStatus(false)
    }
  }, [])

  useEffect(() => { void fetchBrowserStatus() }, [fetchBrowserStatus])

  // 导入成功统一处理：展示后端 message，延迟跳转移动端首页
  // 延迟 1s 让用户看到成功提示再跳转
  const handleImportSuccess = useCallback((result: CookieInjectResult) => {
    message.success(result.message || '导入成功')
    setTimeout(() => {
      globalThis.location.href = '/app/m/'
    }, 1000)
  }, [message])

  // 单浏览器导入：auto_close=true 让后端处理文件锁
  // 为什么用 true：闲鱼进程常驻导致 SQLite 锁，自动关闭可显著提升成功率
  const handleImportFromBrowser = useCallback(async (browser: 'edge' | 'chrome') => {
    setImporting(true)
    try {
      const result = await authApi.importFromBrowser(browser, true)
      if (result.ok) {
        handleImportSuccess(result)
      } else {
        message.error(getResultError(result) || '导入失败，请重试')
      }
    } catch (e) {
      message.error(extractApiError(e, '导入失败，请检查浏览器是否已登录闲鱼'), 3)
    } finally {
      setImporting(false)
    }
  }, [message, handleImportSuccess])

  // 自动导入：后端依次尝试 Edge + Chrome
  const handleAutoImport = useCallback(async () => {
    setImporting(true)
    try {
      const result = await authApi.autoImportFromBrowser()
      if (result.ok) {
        handleImportSuccess(result)
      } else {
        message.error(getResultError(result) || '自动导入失败')
      }
    } catch (e) {
      message.error(extractApiError(e, '自动导入失败，请手动选择浏览器或粘贴 Cookie'), 3)
    } finally {
      setImporting(false)
    }
  }, [message, handleImportSuccess])

  // 手动注入 Cookie：用户从浏览器开发者工具复制 Cookie 字符串粘贴
  const handleInjectCookie = useCallback(async () => {
    const trimmed = cookieText.trim()
    if (!trimmed) {
      message.warning('请粘贴 Cookie 字符串')
      return
    }
    setImporting(true)
    try {
      const result = await authApi.injectCookie(trimmed)
      if (result.ok) {
        handleImportSuccess(result)
      } else {
        message.error(getResultError(result) || 'Cookie 注入失败')
      }
    } catch (e) {
      message.error(extractApiError(e, 'Cookie 注入失败，请检查格式'), 3)
    } finally {
      setImporting(false)
    }
  }, [cookieText, message, handleImportSuccess])

  return (
    <div style={{ padding: 12, maxWidth: 600, margin: '0 auto' }}>
      {/* 浏览器导入 Card */}
      <Card title="浏览器导入" size="small" style={{ marginBottom: 12 }}>
        {loadingStatus ? (
          <div style={{ textAlign: 'center', padding: 16 }}><Spin /></div>
        ) : browserStatus ? (
          <>
            <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }} size={8}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Edge</span>
                <Space size={4}>
                  <Tag color={browserStatus.edge.exists ? 'green' : 'default'}>
                    {browserStatus.edge.exists ? '已安装' : '未安装'}
                  </Tag>
                  {browserStatus.edge.exists && (
                    <Tag color={browserStatus.edge.has_goofish_cookie ? 'green' : 'orange'}>
                      {browserStatus.edge.has_goofish_cookie ? '已登录' : '未登录'}
                    </Tag>
                  )}
                </Space>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Chrome</span>
                <Space size={4}>
                  <Tag color={browserStatus.chrome.exists ? 'green' : 'default'}>
                    {browserStatus.chrome.exists ? '已安装' : '未安装'}
                  </Tag>
                  {browserStatus.chrome.exists && (
                    <Tag color={browserStatus.chrome.has_goofish_cookie ? 'green' : 'orange'}>
                      {browserStatus.chrome.has_goofish_cookie ? '已登录' : '未登录'}
                    </Tag>
                  )}
                </Space>
              </div>
            </Space>
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              <Space style={{ width: '100%' }}>
                <Button
                  block
                  disabled={importing || !browserStatus.edge.exists}
                  onClick={() => { void handleImportFromBrowser('edge') }}
                >
                  从 Edge 导入
                </Button>
                <Button
                  block
                  disabled={importing || !browserStatus.chrome.exists}
                  onClick={() => { void handleImportFromBrowser('chrome') }}
                >
                  从 Chrome 导入
                </Button>
              </Space>
              <Button
                type="primary"
                block
                loading={importing}
                onClick={() => { void handleAutoImport() }}
              >
                自动导入
              </Button>
            </Space>
          </>
        ) : (
          <div style={{ color: '#999', textAlign: 'center', padding: 16 }}>无法获取浏览器状态</div>
        )}
      </Card>

      {/* 手动 Cookie 注入 Card */}
      <Card title="手动 Cookie 注入" size="small">
        <Input.TextArea
          value={cookieText}
          onChange={(e) => setCookieText(e.target.value)}
          placeholder="粘贴 Cookie 字符串（key=value; key=value 格式）"
          rows={6}
          disabled={importing}
          style={{ marginBottom: 12 }}
        />
        <Button
          type="primary"
          block
          loading={importing}
          onClick={() => { void handleInjectCookie() }}
        >
          注入 Cookie
        </Button>
      </Card>
    </div>
  )
}

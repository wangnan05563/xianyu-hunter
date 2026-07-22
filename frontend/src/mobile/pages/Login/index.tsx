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

// 导入流程共享的回调集合：result 失败与 catch 失败分离，保留原 duration 差异
// 为什么用对象：参数过多会降低可读性，命名字段让调用点意图清晰
type RunImportFlowOptions = {
  setImporting: (v: boolean) => void
  apiCall: () => Promise<CookieInjectResult>
  onSuccess: (r: CookieInjectResult) => void
  onResultError: (msg: string) => void
  onCatchError: (msg: string) => void
  fallbackErrorMsg: string
  catchErrorMsg: string
}

// 统一封装 setImporting + try/catch/finally + result.ok 分支的样板代码
// 为什么提取：MobileLogin 内 3 个导入 handler 结构同构，重复 if/else + try/catch
// 导致认知复杂度累积到 27，超过 SonarQube S3776 阈值 15
async function runImportFlow(opts: RunImportFlowOptions) {
  const { setImporting, apiCall, onSuccess, onResultError, onCatchError, fallbackErrorMsg, catchErrorMsg } = opts
  setImporting(true)
  try {
    const result = await apiCall()
    if (result.ok) {
      onSuccess(result)
    } else {
      onResultError(getResultError(result) || fallbackErrorMsg)
    }
  } catch (e) {
    onCatchError(extractApiError(e, catchErrorMsg))
  } finally {
    setImporting(false)
  }
}

// 单浏览器状态展示行。提取为子组件避免在父组件 JSX 内堆叠多个嵌套三元（S3358）
// 并显著降低 MobileLogin 认知复杂度（S3776）
function BrowserStatusRow({
  name,
  exists,
  hasCookie,
}: {
  // readonly 修饰符满足 S6759：组件 props 运行时不应变更
  readonly name: string
  readonly exists: boolean
  readonly hasCookie: boolean
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span>{name}</span>
      <Space size={4}>
        <Tag color={exists ? 'green' : 'default'}>
          {exists ? '已安装' : '未安装'}
        </Tag>
        {exists && (
          <Tag color={hasCookie ? 'green' : 'orange'}>
            {hasCookie ? '已登录' : '未登录'}
          </Tag>
        )}
      </Space>
    </div>
  )
}

// 浏览器导入 Card 内容。用 if 提前 return 替代 loadingStatus ? A : browserStatus ? B : C 嵌套三元（S3358）
function BrowserImportContent({
  loadingStatus,
  browserStatus,
  importing,
  onImportFromEdge,
  onImportFromChrome,
  onAutoImport,
}: {
  readonly loadingStatus: boolean
  readonly browserStatus: BrowserImportStatus | null
  readonly importing: boolean
  readonly onImportFromEdge: () => void
  readonly onImportFromChrome: () => void
  readonly onAutoImport: () => void
}) {
  if (loadingStatus) {
    return <div style={{ textAlign: 'center', padding: 16 }}><Spin /></div>
  }
  if (!browserStatus) {
    return <div style={{ color: '#999', textAlign: 'center', padding: 16 }}>无法获取浏览器状态</div>
  }
  return (
    <>
      <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }} size={8}>
        <BrowserStatusRow
          name="Edge"
          exists={browserStatus.edge.exists}
          hasCookie={browserStatus.edge.has_goofish_cookie}
        />
        <BrowserStatusRow
          name="Chrome"
          exists={browserStatus.chrome.exists}
          hasCookie={browserStatus.chrome.has_goofish_cookie}
        />
      </Space>
      <Space direction="vertical" style={{ width: '100%' }} size={8}>
        <Space style={{ width: '100%' }}>
          <Button
            block
            disabled={importing || !browserStatus.edge.exists}
            onClick={onImportFromEdge}
          >
            从 Edge 导入
          </Button>
          <Button
            block
            disabled={importing || !browserStatus.chrome.exists}
            onClick={onImportFromChrome}
          >
            从 Chrome 导入
          </Button>
        </Space>
        <Button
          type="primary"
          block
          loading={importing}
          onClick={onAutoImport}
        >
          自动导入
        </Button>
      </Space>
    </>
  )
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
  // void 操作符显式丢弃 message.error 的返回值，符合 S6544 期望的 void 返回类型
  const handleImportFromBrowser = useCallback(async (browser: 'edge' | 'chrome') => {
    await runImportFlow({
      setImporting,
      apiCall: () => authApi.importFromBrowser(browser, true),
      onSuccess: handleImportSuccess,
      onResultError: (m) => { void message.error(m) },
      onCatchError: (m) => { void message.error(m, 3) },
      fallbackErrorMsg: '导入失败，请重试',
      catchErrorMsg: '导入失败，请检查浏览器是否已登录闲鱼',
    })
  }, [message, handleImportSuccess])

  // 自动导入：后端依次尝试 Edge + Chrome
  const handleAutoImport = useCallback(async () => {
    await runImportFlow({
      setImporting,
      apiCall: () => authApi.autoImportFromBrowser(),
      onSuccess: handleImportSuccess,
      onResultError: (m) => { void message.error(m) },
      onCatchError: (m) => { void message.error(m, 3) },
      fallbackErrorMsg: '自动导入失败',
      catchErrorMsg: '自动导入失败，请手动选择浏览器或粘贴 Cookie',
    })
  }, [message, handleImportSuccess])

  // 手动注入 Cookie：用户从浏览器开发者工具复制 Cookie 字符串粘贴
  const handleInjectCookie = useCallback(async () => {
    const trimmed = cookieText.trim()
    if (!trimmed) {
      message.warning('请粘贴 Cookie 字符串')
      return
    }
    await runImportFlow({
      setImporting,
      apiCall: () => authApi.injectCookie(trimmed),
      onSuccess: handleImportSuccess,
      onResultError: (m) => { void message.error(m) },
      onCatchError: (m) => { void message.error(m, 3) },
      fallbackErrorMsg: 'Cookie 注入失败',
      catchErrorMsg: 'Cookie 注入失败，请检查格式',
    })
  }, [cookieText, message, handleImportSuccess])

  return (
    <div style={{ padding: 12, maxWidth: 600, margin: '0 auto' }}>
      {/* 浏览器导入 Card */}
      <Card title="浏览器导入" size="small" style={{ marginBottom: 12 }}>
        <BrowserImportContent
          loadingStatus={loadingStatus}
          browserStatus={browserStatus}
          importing={importing}
          onImportFromEdge={() => { void handleImportFromBrowser('edge') }}
          onImportFromChrome={() => { void handleImportFromBrowser('chrome') }}
          onAutoImport={() => { void handleAutoImport() }}
        />
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

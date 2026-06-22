import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Card,
  Button,
  Input,
  Tabs,
  message,
  Spin,
  Alert,
  Upload,
  Typography,
  Space,
  Tag,
  Divider,
  Progress,
} from 'antd'
import {
  LoginOutlined,
  ImportOutlined,
  CopyOutlined,
  ChromeOutlined,
  UploadOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
  GlobalOutlined,
  KeyOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  ClearOutlined,
} from '@ant-design/icons'
import { authApi } from '../../api'
import type { LoginStatus, SavedCookieInfo } from '../../api/auth'

const { TextArea } = Input
const { Text, Title } = Typography

// 登录页面：独立于 MainLayout，提供多种登录方式
export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirect = searchParams.get('redirect') || '/'

  // 当前登录态信息
  const [cookieInfo, setCookieInfo] = useState<SavedCookieInfo | null>(null)
  const [checkingAuth, setCheckingAuth] = useState(true)

  // Cookie 注入 Tab 状态 — 分字段输入（参考旧版 dashboard 设计）
  const COOKIE_KEYS = [
    { key: '_m_h5_tk', label: '安全令牌', hint: '每小时自动刷新，过期后搜索会报签名错误' },
    { key: 'cookie2', label: '会话ID', hint: '' },
    { key: 'sgcookie', label: '安全Cookie', hint: '' },
    { key: 'unb', label: '用户ID', hint: '' },
  ] as const
  const [cookieFields, setCookieFields] = useState<Record<string, string>>({
    _m_h5_tk: '', cookie2: '', sgcookie: '', unb: '',
  })
  const [injecting, setInjecting] = useState(false)
  const [autoFilling, setAutoFilling] = useState(false)
  const [autoFillResult, setAutoFillResult] = useState<{ text: string; error: boolean } | null>(null)

  // 浏览器导入 Tab 状态
  const [browserStatus, setBrowserStatus] = useState<{
    edge: { exists: boolean; has_goofish_cookie: boolean }
    chrome: { exists: boolean; has_goofish_cookie: boolean }
  } | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<string | null>(null)

  // 浏览器窗口登录 Tab 状态
  const [loginStatus, setLoginStatus] = useState<LoginStatus | null>(null)
  const [pollTimer, setPollTimer] = useState<ReturnType<typeof setInterval> | null>(null)

  const pollRef = useRef(pollTimer)
  pollRef.current = pollTimer

  // 页面加载时检查当前登录态 + 填充已保存的 Cookie 值
  useEffect(() => {
    // 不再因已登录而跳转 — 用户点击「登录管理」就是为了管理 Cookie
    authApi.getMe().then((data) => {
      // 仅记录状态，不跳转
    }).catch(() => {})
      .finally(() => setCheckingAuth(false))

    // 并行获取：Cookie 摘要、浏览器状态、以及已保存的具体 Cookie 值（用于返显）
    authApi.getSavedCookieInfo().then(setCookieInfo).catch(() => {})
    authApi.getBrowserImportStatus().then(setBrowserStatus).catch(() => {})

    // 自动获取已保存的 cookie 值填充到输入框（让用户看到当前值）
    fetch('/api/auth/cookie/fetch-keys?keys=_m_h5_tk,cookie2,sgcookie,unb', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok && data.cookies) {
          const updated = { ...cookieFields }
          let filled = 0
          for (const ck of COOKIE_KEYS) {
            if (data.cookies[ck.key]) {
              updated[ck.key] = data.cookies[ck.key]
              filled++
            }
          }
          if (filled > 0) setCookieFields(updated)
        }
      })
      .catch(() => {})
  }, [])

  // 清理轮询定时器
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // 登录成功后跳转
  const onLoginSuccess = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      setPollTimer(null)
    }
    message.success('登录成功，正在跳转...')
    // 等待后端设置 cookie 后再跳转
    setTimeout(() => navigate(redirect, { replace: true }), 800)
  }, [navigate, redirect])

  // ===== Cookie 注入（分字段合并后提交） =====
  const handleInjectCookie = async () => {
    const hasValue = COOKIE_KEYS.some((ck) => cookieFields[ck.key]?.trim())
    if (!hasValue) {
      message.warning('请至少填写一个 Cookie 值')
      return
    }
    setInjecting(true)
    try {
      // 将分字段拼接为旧版格式的 cookie 字符串
      const parts = COOKIE_KEYS.filter((ck) => cookieFields[ck.key]?.trim())
        .map((ck) => `${ck.key}=${cookieFields[ck.key].trim()}`)
      const cookieString = parts.join('; ')
      const result = await authApi.injectCookie(cookieString)
      if (result.ok) {
        message.success(result.message || 'Cookie 注入成功')
        onLoginSuccess()
      } else {
        message.error(result.error || 'Cookie 注入失败')
      }
    } catch (err: any) {
      message.error(err?.response?.data?.error || '请求失败')
    } finally {
      setInjecting(false)
    }
  }

  // 清空所有字段
  const handleClearCookies = () => {
    setCookieFields({ _m_h5_tk: '', cookie2: '', sgcookie: '', unb: '' })
    setAutoFillResult(null)
  }

  // 从浏览器自动获取（填充到各字段）
  const handleAutoFillFromBrowser = async () => {
    setAutoFilling(true)
    setAutoFillResult(null)
    try {
      const r = await fetch('/api/auth/cookie/fetch-keys?keys=_m_h5_tk,cookie2,sgcookie,unb', {
        credentials: 'include',
      })
      const data = await r.json()
      if (data.ok && data.cookies) {
        let filled = 0
        const updated = { ...cookieFields }
        for (const ck of COOKIE_KEYS) {
          if (data.cookies[ck.key]) {
            updated[ck.key] = data.cookies[ck.key]
            filled++
          }
        }
        setCookieFields(updated)
        const srcLabel = data.source === 'cookie_store_json_fallback'
          ? '（回退到上次保存的 Cookie）'
          : ''
        setAutoFillResult({ text: `成功获取 ${filled} 个 Cookie 值${srcLabel}`, error: data.source === 'cookie_store_json_fallback' })
      } else {
        setAutoFillResult({ text: data.hint || data.error || '未找到 Cookie', error: true })
      }
    } catch {
      setAutoFillResult({ text: '请求失败', error: true })
    } finally {
      setAutoFilling(false)
    }
  }

  // ===== Cookie 文件上传 =====
  const handleFileUpload = async (file: File) => {
    setInjecting(true)
    try {
      const result = await authApi.importCookieFile(file)
      if (result.ok) {
        message.success(result.message || 'Cookie 文件导入成功')
        onLoginSuccess()
      } else {
        message.error(result.error || 'Cookie 文件导入失败')
      }
    } catch (err: any) {
      message.error(err?.response?.data?.error || '请求失败')
    } finally {
      setInjecting(false)
    }
    // 阻止 Upload 组件的默认上传行为
    return false
  }

  // ===== 浏览器导入 =====
  const handleImportFromBrowser = async (browser: 'edge' | 'chrome') => {
    setImporting(true)
    setImportResult(null)
    try {
      const result = await authApi.importFromBrowser(browser)
      if (result.ok) {
        setImportResult(result.message || `成功从 ${browser} 导入 ${result.injected} 个 Cookie`)
        message.success(setImportResult as unknown as string)
        onLoginSuccess()
      } else {
        setImportResult(result.error || '导入失败')
        message.error(result.error || '导入失败')
      }
    } catch (err: any) {
      const errMsg = err?.response?.data?.error || '请求失败'
      setImportResult(errMsg)
      message.error(errMsg)
    } finally {
      setImporting(false)
    }
  }

  // 打开系统浏览器到闲鱼
  const handleOpenBrowser = async () => {
    try {
      const result = await authApi.openBrowserToLogin()
      if (result.ok) {
        message.info(result.message || '已打开浏览器，请登录后返回此页面')
      } else {
        message.error(result.error || '无法打开浏览器')
      }
    } catch {
      message.error('请求失败')
    }
  }

  // ===== 浏览器窗口登录（Playwright） =====
  const handleStartBrowserLogin = async () => {
    try {
      const result = await authApi.startBrowserLogin()
      if (result.ok) {
        message.info('浏览器窗口已启动，请在窗口中完成登录')
        startPolling()
      } else {
        message.error(result.error || '启动失败')
      }
    } catch (err: any) {
      message.error(err?.response?.data?.error || '请求失败')
    }
  }

  // 开始轮询登录状态
  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    const timer = setInterval(async () => {
      try {
        const status = await authApi.getLoginStatus()
        setLoginStatus(status)
        if (status.status === 'success') {
          onLoginSuccess()
        } else if (['cancelled', 'error', 'timeout'].includes(status.status)) {
          clearInterval(pollRef.current!)
          setPollTimer(null)
        }
      } catch {
        // 轮询失败不中断，继续尝试
      }
    }, 2000)
    setPollTimer(timer)
  }

  // 取消登录
  const handleCancelLogin = async () => {
    try {
      await authApi.cancelLogin()
      if (pollRef.current) {
        clearInterval(pollRef.current)
        setPollTimer(null)
      }
      setLoginStatus(null)
      message.info('已取消登录')
    } catch {
      message.error('取消失败')
    }
  }

  if (checkingAuth) {
    return (
      <div style={{
        display: 'flex', justifyContent: 'center', alignItems: 'center',
        height: '100vh', background: 'var(--xh-bg-layout)',
      }}>
        <Spin size="large" tip="正在检查登录状态..."><div /></Spin>
      </div>
    )
  }

  const tabItems = [
    {
      key: 'cookie-inject',
      label: (
        <span><KeyOutlined /> Cookie 注入</span>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 顶部操作栏：自动获取 + 当前状态 + 清空 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Button
              size="small"
              icon={<GlobalOutlined />}
              loading={autoFilling}
              onClick={handleAutoFillFromBrowser}
            >
              {autoFilling ? '读取中…' : '从浏览器自动获取'}
            </Button>
            {autoFillResult && (
              <span style={{ fontSize: 12, color: autoFillResult.error ? '#e65100' : '#52c41a' }}>
                {autoFillResult.text}
              </span>
            )}
            {COOKIE_KEYS.some((ck) => cookieFields[ck.key]?.trim()) && (
              <Button size="small" icon={<ClearOutlined />} onClick={handleClearCookies}>
                清空
              </Button>
            )}
          </div>

          {/* 已有 Cookie 状态提示 */}
          {cookieInfo?.has_cookies && (
            <Alert
              type="info"
              showIcon={false}
              message={
                <span style={{ fontSize: 12 }}>
                  已保存 <strong>{cookieInfo.cookie_count}</strong> 个 Cookie
                  {cookieInfo.method && `（来源: ${cookieInfo.method}）`}
                  {(cookieInfo.key_cookies_found?.length ?? 0) > 0 && (
                    <span>，关键: {cookieInfo.key_cookies_found!.join(', ')}</span>
                  )}
                </span>
              }
              style={{ marginBottom: 4 }}
            />
          )}

          {/* 分字段输入 */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
          }}>
            {COOKIE_KEYS.map((ck) => (
              <div key={ck.key} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Tag color="blue" style={{ fontSize: 11, fontFamily: 'monospace' }}>{ck.key}</Tag>
                  <span style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>{ck.label}</span>
                </div>
                <Input
                  placeholder={`粘贴 ${ck.key} 的值`}
                  value={cookieFields[ck.key]}
                  onChange={(e) => setCookieFields((prev) => ({ ...prev, [ck.key]: e.target.value }))}
                  style={{ fontFamily: 'monospace', fontSize: 12 }}
                  disabled={injecting}
                />
                {ck.hint && (
                  <span style={{ fontSize: 10, color: '#e65100' }}>{ck.hint}</span>
                )}
              </div>
            ))}
          </div>

          {/* 高级：整段粘贴（兼容旧格式） */}
          <details style={{ marginTop: 4 }}>
            <summary style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', cursor: 'pointer' }}>
              高级：粘贴整段 Cookie 文本
            </summary>
            <TextArea
              rows={3}
              placeholder="_m_h5_tk=xxx; cookie2=xxx; sgcookie=xxx; unb=xxx"
              onBlur={(e) => {
                const text = e.target.value.trim()
                if (!text) return
                const updated = { ...cookieFields }
                for (const ck of COOKIE_KEYS) {
                  const match = text.match(new RegExp(`${ck.key}=([^;\\s]+)`))
                  if (match?.[1]) updated[ck.key] = match[1]
                }
                setCookieFields(updated)
              }}
              style={{ fontFamily: 'monospace', fontSize: 11, marginTop: 6 }}
            />
          </details>

          {/* 操作按钮 */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Button
              type="primary"
              icon={<KeyOutlined />}
              loading={injecting}
              onClick={handleInjectCookie}
              disabled={!COOKIE_KEYS.some((ck) => cookieFields[ck.key]?.trim())}
              style={{ background: '#FF6200', borderColor: '#FF6200' }}
            >
              注入 Cookie 登录
            </Button>

            <Divider type="vertical" style={{ height: 24 }} />

            <Text type="secondary" style={{ fontSize: 11 }}>或</Text>

            <Upload
              accept=".txt,.json,.csv"
              maxCount={1}
              showUploadList={false}
              beforeUpload={handleFileUpload}
            >
              <Button icon={<UploadOutlined />} size="small" loading={injecting}>
                上传文件
              </Button>
            </Upload>
          </div>
        </div>
      ),
    },
    {
      key: 'browser-import',
      label: (
        <span><ChromeOutlined /> 浏览器导入</span>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Alert
            type="info"
            showIcon
            message="从系统浏览器自动获取闲鱼登录状态"
            description="如果你已在 Edge 或 Chrome 中登录过闲鱼，可以直接导入 Cookie，无需重新扫码"
            style={{ marginBottom: 8 }}
          />

          {/* 浏览器状态检测 */}
          {browserStatus && (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {(['edge', 'chrome'] as const).map((b) => (
                <Tag
                  key={b}
                  icon={<GlobalOutlined />}
                  color={browserStatus[b].has_goofish_cookie ? 'green' : browserStatus[b].exists ? 'default' : 'red'}
                  style={{ fontSize: 13, padding: '4px 12px' }}
                >
                  {b === 'edge' ? 'Edge' : 'Chrome'}
                  {!browserStatus[b].exists ? ' 未安装' : browserStatus[b].has_goofish_cookie ? ' 可导入' : ' 未检测到闲鱼 Cookie'}
                </Tag>
              ))}
            </div>
          )}

          {/* 操作按钮 */}
          <Space wrap>
            <Button
              type="primary"
              icon={<ImportOutlined />}
              loading={importing}
              onClick={() => handleImportFromBrowser('edge')}
              disabled={!browserStatus?.edge?.exists}
              style={{ background: '#FF6200', borderColor: '#FF6200' }}
            >
              从 Edge 导入
            </Button>
            <Button
              icon={<ImportOutlined />}
              loading={importing}
              onClick={() => handleImportFromBrowser('chrome')}
              disabled={!browserStatus?.chrome?.exists}
            >
              从 Chrome 导入
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleOpenBrowser}>
              打开闲鱼网页
            </Button>
          </Space>

          {/* 导入结果提示 */}
          {importResult && (
            <Alert
              type={importResult.includes('成功') ? 'success' : 'error'}
              message={importResult}
              showIcon
              closable
              onClose={() => setImportResult(null)}
            />
          )}

          <Divider plain style={{ margin: '8px 0' }}>
            <Text type="secondary">或使用其他方式</Text>
          </Divider>

          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => {
              authApi.getBrowserImportStatus().then(setBrowserStatus).catch(() => {})
              message.info('已刷新浏览器状态')
            }}>
              刷新检测
            </Button>
          </Space>
        </div>
      ),
    },
    {
      key: 'browser-login',
      label: (
        <span><LoginOutlined /> 浏览器登录</span>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Alert
            type="info"
            showIcon
            message="弹出浏览器窗口登录"
            description="启动 Playwright 浏览器窗口，在窗口中手动登录闲鱼。适合浏览器导入失败或需要重新登录的场景。"
          />

          {!loginStatus || loginStatus.status === 'idle' ? (
            <Button
              type="primary"
              size="large"
              icon={<LoginOutlined />}
              onClick={handleStartBrowserLogin}
              style={{ background: '#FF6200', borderColor: '#FF6200', width: 'fit-content' }}
            >
              启动浏览器窗口登录
            </Button>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* 登录进度 */}
              <div style={{
                padding: 16, borderRadius: 8,
                background: loginStatus.status === 'success' ? '#f6ffed' : '#fffbe6',
                border: `1px solid ${loginStatus.status === 'success' ? '#b7eb8f' : '#ffe58f'}`,
              }}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {loginStatus.status === 'success' ? (
                      <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                    ) : (
                      <Spin size="small" />
                    )}
                    <Text strong>{loginStatus.message}</Text>
                  </div>
                  {loginStatus.elapsed > 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      已用时 {Math.floor(loginStatus.elapsed / 60)}分{Math.floor(loginStatus.elapsed % 60)}秒
                    </Text>
                  )}
                  {/* 进度条：给用户视觉反馈 */}
                  {loginStatus.status === 'running' && (
                    <Progress
                      percent={Math.min(95, Math.floor((loginStatus.elapsed / 300) * 100))}
                      showInfo={false}
                      strokeColor="#FF6200"
                      size="small"
                    />
                  )}
                </Space>
              </div>

              {/* 取消按钮 */}
              {!['success', 'cancelled', 'error', 'timeout'].includes(loginStatus.status) && (
                <Button icon={<SwapOutlined />} onClick={handleCancelLogin}>
                  取消登录
                </Button>
              )}

              {/* 错误/超时重试 */}
              {['error', 'timeout'].includes(loginStatus.status) && (
                <Button type="primary" icon={<ReloadOutlined />} onClick={handleStartBrowserLogin}
                  style={{ background: '#FF6200', borderColor: '#FF6200' }}>
                  重新登录
                </Button>
              )}
            </div>
          )}
        </div>
      ),
    },
  ]

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: 'var(--xh-bg-layout)', padding: 24,
    }}>
      <Card
        style={{
          width: '100%', maxWidth: 560,
          borderRadius: 12,
          boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
        }}
        styles={{ body: { padding: '32px 24px 24px' } }}
      >
        {/* 品牌头部 */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: 'linear-gradient(135deg, #FF6200, #FF8C00)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 12px', fontSize: 28, color: '#fff', fontWeight: 700,
          }}>
            闲
          </div>
          <Title level={4} style={{ margin: 0 }}>闲鱼猎人 - 登录</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            选择一种方式完成闲鱼账号认证
          </Text>
        </div>

        <Tabs items={tabItems} centered />
      </Card>
    </div>
  )
}

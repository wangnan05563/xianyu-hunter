import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { TipButton } from '@/components/TipButton'
import {
  Card,
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
  Modal,
  theme,
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
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { authApi } from '../../api'
import type { LoginStatus, SavedCookieInfo } from '../../api/auth'
import TidalForagers from '../../components/TidalForagers'
import { useTheme } from '../../contexts/ThemeContext'
import { API_BASE } from '../../utils/apiBase'

const { TextArea } = Input
const { Text, Title } = Typography

// 解析 Cookie 文本，支持多种粘贴格式：
// - 标准 Cookie 头：key1=value1; key2=value2
// - 换行分隔（从开发者工具表格复制）：key1=value1\nkey2=value2
// - 带前缀的请求头：Cookie: key1=value1; key2=value2
// - 末尾分号：key1=value1; key2=value2;
// 值中可能包含 = 号，所以只按第一个 = 分割
const parseCookieText = (text: string): Record<string, string> => {
  const result: Record<string, string> = {}
  if (!text) return result

  // 移除可能的 "Cookie:" 前缀（从请求头复制的情况）
  const cleaned = text.replace(/^Cookie:\s*/i, '').trim()
  if (!cleaned) return result

  // 支持分号、换行、逗号作为键值对分隔符
  const parts = cleaned.split(/[;\n\r,]+/)
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue

    const eqIndex = trimmed.indexOf('=')
    if (eqIndex === -1) continue

    const key = trimmed.substring(0, eqIndex).trim()
    const value = trimmed.substring(eqIndex + 1).trim()

    // 过滤无效 key（必须符合 Cookie 命名规范）和空值
    // S6535：字符类中 - 不需转义
    if (!key || !/^[a-zA-Z0-9_-]+$/.test(key)) continue
    if (!value) continue

    result[key] = value
  }

  return result
}

const phaseLabel = (phase?: LoginStatus['phase']) => {
  switch (phase) {
    case 'pending': return '初始化'
    case 'starting': return '启动浏览器'
    case 'opening': return '打开闲鱼'
    case 'waiting': return '等待登录'
    case 'already_logged': return '验证已有登录'
    case 'running': return '处理中'
    default: return ''
  }
}

const timingLabel: Record<string, string> = {
  launch_context_sec: '启动浏览器',
  new_page_sec: '新建页面',
  goto_home_sec: '打开闲鱼',
  initial_cookie_read_sec: '读取 Cookie',
  verify_personal_sec: '验证登录',
  storage_state_sec: '保存状态',
  export_cookies_sec: '导出 Cookie',
}

const formatTimings = (timings?: Record<string, number>) => {
  if (!timings) return ''
  return Object.entries(timings)
    .filter(([, value]) => Number.isFinite(value))
    .map(([key, value]) => `${timingLabel[key] || key} ${Number(value).toFixed(1)}s`)
    .join(' · ')
}

// Cookie 字段元信息：key + 中文标签 + 输入提示
// 为什么提到模块级：静态数据避免每次渲染重建，且被多处辅助函数引用
const COOKIE_KEYS = [
  { key: '_m_h5_tk', label: '安全令牌', hint: '每小时自动刷新，过期后搜索会报签名错误' },
  { key: 'cookie2', label: '会话ID', hint: '' },
  { key: 'sgcookie', label: '安全Cookie', hint: '' },
  { key: 'unb', label: '用户ID', hint: '' },
] as const

// 空字段模板：handleAutoFillFromBrowser 用此作为 prev 重置字段，避免浏览器残留值干扰
const EMPTY_COOKIE_FIELDS: Record<string, string> = {
  _m_h5_tk: '', cookie2: '', sgcookie: '', unb: '',
}

// 把后端返回的 cookies 应用到字段对象上，返回新对象 + matched 列表
// 为什么提取：useEffect 自动填充、handleParsePaste、handleAutoFillFromBrowser 三处都用相同循环
const applyCookiesToFields = (
  cookies: Record<string, string>,
  prev: Record<string, string>,
): { updated: Record<string, string>; filled: number; matched: string[] } => {
  const updated = { ...prev }
  const matched: string[] = []
  for (const ck of COOKIE_KEYS) {
    if (cookies[ck.key]) {
      updated[ck.key] = cookies[ck.key]
      matched.push(ck.key)
    }
  }
  return { updated, filled: matched.length, matched }
}

// 拼接非空字段为 cookie 字符串：key1=value1; key2=value2
// 为什么提取：handleInjectCookie 内的 filter+map+join 链提取后主流程语义更清晰
const buildCookieString = (fields: Record<string, string>): string => {
  return COOKIE_KEYS
    .filter((ck) => fields[ck.key]?.trim())
    .map((ck) => `${ck.key}=${fields[ck.key].trim()}`)
    .join('; ')
}

// 根据 fetch-keys 接口返回的 source 生成用户友好的来源说明标签
// 为什么提取：handleAutoFillFromBrowser 中嵌套 if/else if，提取后降低复杂度
const sourceLabel = (source?: string): string => {
  if (source === 'cookie_store_json_fallback') return '（回退到上次保存的 Cookie）'
  if (source === 'playwright_cdp') return '（来自项目浏览器）'
  return ''
}

// 格式化浏览器导入结果：有 hint 时拼成多行，无 hint 时只返回错误信息
// 为什么提取：handleImportFromBrowser 的失败分支与 catch 分支都用相同拼接逻辑
const formatImportResult = (errMsg: string, hint?: string): string => {
  return hint ? `${errMsg}\n${hint}` : errMsg
}

// 从 axios 错误对象中提取浏览器导入错误信息（errMsg + hint）
// 为什么提取：catch 块里多个 ?. 链 + 默认值，提取后主流程更清晰
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const extractImportBrowserError = (err: any): { errMsg: string; hint: string } => {
  const errMsg = err?.response?.data?.error || '请求失败'
  const hint = err?.response?.data?.hint || ''
  return { errMsg, hint }
}

// S3776 修复：将轮询 tick 从 startPolling 内嵌套提取到模块级
// 原嵌套层级 3（startPolling → tick → if/else if → if），提取后降至 1
const POLL_TERMINAL_STATUSES = ['cancelled', 'error', 'timeout', 'idle'] as const
const pollLoginTick = async (
  setLoginStatus: (s: LoginStatus | null) => void,
  onSuccess: () => void,
  stopPolling: () => void,
) => {
  try {
    const status = await authApi.getLoginStatus()
    setLoginStatus(status)
    if (status.status === 'success') {
      onSuccess()
    } else if (POLL_TERMINAL_STATUSES.includes(status.status as typeof POLL_TERMINAL_STATUSES[number])) {
      // idle 表示后端已重置（web 进程重启或心跳超时清理），
      // 停止轮询并清空 loginStatus 让前端回到初始按钮状态
      stopPolling()
      if (status.status === 'idle') {
        setLoginStatus(null)
      }
    }
  } catch {
    // 轮询失败不中断，继续尝试
  }
}

// 浏览器状态 Tag 颜色：有闲鱼 Cookie=绿，已安装但无 Cookie=默认，未安装=红
// 为什么提取：原 tabItems 内 IIFE 含 if/if/return，提取后子组件 JSX 更扁平
const browserTagColor = (status: { exists: boolean; has_goofish_cookie: boolean }): string => {
  if (status.has_goofish_cookie) return 'green'
  if (status.exists) return 'default'
  return 'red'
}

// 浏览器状态 Tag 文本：未安装/可导入/未检测到闲鱼 Cookie
const browserTagText = (status: { exists: boolean; has_goofish_cookie: boolean }): string => {
  if (!status.exists) return ' 未安装'
  if (status.has_goofish_cookie) return ' 可导入'
  return ' 未检测到闲鱼 Cookie'
}

// S3776 修复：浏览器登录 Tab 提取为子组件
// 原主函数 tabItems 内含 8 处条件判断（||/&&/?:/includes），提取后主函数复杂度降 ~8
function BrowserLoginTab({
  loginStatus, startingBrowser, onStart, onCancel,
}: {
  readonly loginStatus: LoginStatus | null
  readonly startingBrowser: boolean
  readonly onStart: () => void
  readonly onCancel: () => void
}) {
  const { token: themeToken } = theme.useToken()
  // 终态判断：success/cancelled/error/timeout 都允许重新登录
  // 为什么复用变量：原代码两处 .includes() 互斥，提取为 isTerminal 消除 2 处重复 .includes 调用
  const isTerminal = loginStatus != null && ['success', 'cancelled', 'error', 'timeout'].includes(loginStatus.status)
  const showStartButton = !loginStatus || loginStatus.status === 'idle'
  // 进度卡片背景：成功用绿色，进行中用黄色（提取变量消除 2 处三元）
  const progressBg = loginStatus?.status === 'success' ? '#f6ffed' : '#fffbe6'
  const progressBorder = loginStatus?.status === 'success' ? '#b7eb8f' : '#ffe58f'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Alert
        type="info"
        showIcon
        message="弹出浏览器窗口登录"
        description="启动 Playwright 浏览器窗口，在窗口中手动登录闲鱼。适合浏览器导入失败或需要重新登录的场景。"
      />

      {showStartButton ? (
        <TipButton
          tip="启动浏览器窗口并手动登录闲鱼"
          type="primary"
          size="large"
          icon={<LoginOutlined />}
          onClick={onStart}
          loading={startingBrowser}
          style={{ background: '#FF6200', borderColor: '#FF6200', width: 'fit-content' }}
        >
          启动浏览器窗口登录
        </TipButton>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* 登录进度 */}
          <div style={{ padding: 16, borderRadius: 8, background: progressBg, border: `1px solid ${progressBorder}` }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {loginStatus?.status === 'success' ? (
                  <CheckCircleOutlined style={{ color: themeToken.colorSuccess, fontSize: 20 }} />
                ) : (
                  <Spin size="small" />
                )}
                <Text strong>{loginStatus?.message}</Text>
              </div>
              {loginStatus && loginStatus.elapsed > 0 && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  已用时 {Math.floor(loginStatus.elapsed / 60)}分{Math.floor(loginStatus.elapsed % 60)}秒
                </Text>
              )}
              {loginStatus && (loginStatus.phase || loginStatus.child_elapsed != null) && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {phaseLabel(loginStatus.phase) || '当前阶段'}
                  {/* S7735：避免取反条件，改为 == null 优先返回空串 */}
                  {loginStatus.child_elapsed == null ? '' : ` ${Number(loginStatus.child_elapsed).toFixed(1)}秒`}
                  {loginStatus.wait_elapsed == null ? '' : `（等待登录 ${loginStatus.wait_elapsed}秒）`}
                </Text>
              )}
              {loginStatus && formatTimings(loginStatus.timings) && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  阶段耗时：{formatTimings(loginStatus.timings)}
                </Text>
              )}
              {/* 进度条：给用户视觉反馈 */}
              {loginStatus?.status === 'running' && (
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
          {!isTerminal && (
            <TipButton tip="取消当前登录过程" icon={<SwapOutlined />} onClick={onCancel}>
              取消登录
            </TipButton>
          )}

          {/* 终态重试：success/cancelled/error/timeout 都允许重新登录
              - error/timeout：常规重试
              - cancelled：用户主动取消后可能想重新尝试
              - success：跳转失败的兜底（onLoginSuccess 未成功跳转时用户可手动重试） */}
          {isTerminal && (
            <TipButton type="primary" tip="重新启动浏览器窗口登录" icon={<ReloadOutlined />} onClick={onStart}
              loading={startingBrowser}
              style={{ background: '#FF6200', borderColor: '#FF6200' }}>
              重新登录
            </TipButton>
          )}
        </div>
      )}
    </div>
  )
}

// S3776 修复：Cookie 注入 Tab 提取为子组件
// 原主函数 tabItems 内含 ~10 处条件判断（&&/?:），提取后主函数复杂度降 ~10
function CookieInjectTab({
  cookieFields, setCookieFields, injecting, autoFilling, autoFillResult,
  pasteText, parseResult, cookieInfo,
  onInject, onAutoFill, onClear, onParsePaste, onPaste, onFileUpload,
}: {
  readonly cookieFields: Record<string, string>
  readonly setCookieFields: React.Dispatch<React.SetStateAction<Record<string, string>>>
  readonly injecting: boolean
  readonly autoFilling: boolean
  readonly autoFillResult: { text: string; error: boolean } | null
  readonly pasteText: string
  readonly parseResult: { total: number; matched: string[]; missing: string[] } | null
  readonly cookieInfo: SavedCookieInfo | null
  readonly onInject: () => void
  readonly onAutoFill: () => void
  readonly onClear: () => void
  readonly onParsePaste: (text: string) => void
  readonly onPaste: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void
  readonly onFileUpload: (file: File) => boolean | Promise<boolean>
}) {
  const { isDark } = useTheme()
  const { token: themeToken } = theme.useToken()
  const hasAnyCookie = COOKIE_KEYS.some((ck) => cookieFields[ck.key]?.trim())
  const keyCookiesFound = cookieInfo?.key_cookies_found ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 顶部操作栏：自动获取 + 当前状态 + 清空 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <TipButton
          tip="从系统浏览器读取 Cookie 并填充"
          size="small"
          icon={<GlobalOutlined />}
          loading={autoFilling}
          onClick={onAutoFill}
        >
          {autoFilling ? '读取中…' : '从浏览器自动获取'}
        </TipButton>
        {autoFillResult && (
          <span style={{ fontSize: 12, color: autoFillResult.error ? themeToken.colorError : themeToken.colorSuccess }}>
            {autoFillResult.text}
          </span>
        )}
        {hasAnyCookie && (
          <TipButton tip="清空已填写的 Cookie 字段" size="small" icon={<ClearOutlined />} onClick={onClear}>
            清空
          </TipButton>
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
              {keyCookiesFound.length > 0 && (
                <span>，关键: {keyCookiesFound.join(', ')}</span>
              )}
            </span>
          }
          style={{ marginBottom: 4 }}
        />
      )}

      {/* 快速粘贴：从浏览器开发者工具全量复制 Cookie 键值对后直接粘贴 */}
      <div style={{
        padding: 12,
        borderRadius: 8,
        background: isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.02)',
        border: `1px dashed ${themeToken.colorBorder}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: themeToken.colorText }}>
            <CopyOutlined style={{ marginRight: 4 }} />
            快速粘贴 Cookie
          </span>
          <Text type="secondary" style={{ fontSize: 10 }}>
            支持格式：key=value; key=value 或换行分隔
          </Text>
        </div>
        <TextArea
          rows={3}
          placeholder="从此处粘贴从浏览器复制的 Cookie，例如：&#10;_m_h5_tk=xxx; cookie2=xxx; sgcookie=xxx; unb=xxx"
          value={pasteText}
          onChange={(e) => onParsePaste(e.target.value)}
          onPaste={onPaste}
          style={{ fontFamily: 'monospace', fontSize: 11 }}
          disabled={injecting}
          autoComplete="off"
          name="cookie-paste-area"
          spellCheck={false}
        />
        {/* 解析结果反馈 */}
        {parseResult && (
          <div style={{ marginTop: 6, fontSize: 11 }}>
            {parseResult.total > 0 ? (
              <Space size={4} wrap>
                <span style={{ color: themeToken.colorTextSecondary }}>
                  识别到 <strong style={{ color: themeToken.colorPrimary }}>{parseResult.total}</strong> 个 Cookie
                </span>
                {parseResult.matched.length > 0 && (
                  <span style={{ color: themeToken.colorSuccess }}>
                    ✓ 已填充: {parseResult.matched.join(', ')}
                  </span>
                )}
                {parseResult.missing.length > 0 && (
                  <span style={{ color: themeToken.colorWarning }}>
                    ⚠ 未找到: {parseResult.missing.join(', ')}
                  </span>
                )}
              </Space>
            ) : (
              <span style={{ color: themeToken.colorError }}>
                未识别到有效的 Cookie 键值对，请检查格式
              </span>
            )}
          </div>
        )}
      </div>

      {/* 分字段输入（用于精细调整） */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
      }}>
        {COOKIE_KEYS.map((ck) => (
          <div key={ck.key} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Tag color="blue" style={{ fontSize: 11, fontFamily: 'monospace' }}>{ck.key}</Tag>
              <span style={{ fontSize: 11, color: themeToken.colorTextSecondary, fontWeight: 500 }}>{ck.label}</span>
            </div>
            <Input
              placeholder={`粘贴 ${ck.key} 的值`}
              value={cookieFields[ck.key]}
              onChange={(e) => setCookieFields((prev) => ({ ...prev, [ck.key]: e.target.value }))}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
              disabled={injecting}
              autoComplete="off"
              name={`cookie-${ck.key}`}
              spellCheck={false}
            />
            {ck.hint && (
              <span style={{ fontSize: 10, color: themeToken.colorWarning, fontWeight: 500 }}>{ck.hint}</span>
            )}
          </div>
        ))}
      </div>

      {/* 操作按钮 */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <TipButton
          tip="注入 Cookie 完成登录"
          type="primary"
          icon={<KeyOutlined />}
          loading={injecting}
          onClick={onInject}
          disabled={!hasAnyCookie}
          style={{ background: '#FF6200', borderColor: '#FF6200' }}
        >
          注入 Cookie 登录
        </TipButton>

        <Divider type="vertical" style={{ height: 24 }} />

        <Text type="secondary" style={{ fontSize: 11 }}>或</Text>

        <Upload
          accept=".txt,.json,.csv"
          maxCount={1}
          showUploadList={false}
          beforeUpload={onFileUpload}
        >
          <TipButton tip="从文件导入 Cookie" icon={<UploadOutlined />} size="small" loading={injecting}>
            上传文件
          </TipButton>
        </Upload>
      </div>
    </div>
  )
}

// S3776 修复：浏览器导入 Tab 提取为子组件
// 原主函数 tabItems 内含 2 处 IIFE + 多处条件判断，提取后用 browserTagColor/browserTagText 替代 IIFE
function BrowserImportTab({
  browserStatus, importing, importResult,
  onImport, onOpenBrowser, onRefreshStatus, onClearImportResult,
}: {
  readonly browserStatus: {
    edge: { exists: boolean; has_goofish_cookie: boolean }
    chrome: { exists: boolean; has_goofish_cookie: boolean }
  } | null
  readonly importing: boolean
  readonly importResult: string | null
  readonly onImport: (browser: 'edge' | 'chrome', autoClose?: boolean) => void
  readonly onOpenBrowser: () => void
  readonly onRefreshStatus: () => void
  readonly onClearImportResult: () => void
}) {
  return (
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
          {(['edge', 'chrome'] as const).map((b) => {
            const status = browserStatus[b]
            return (
              <Tag
                key={b}
                icon={<GlobalOutlined />}
                color={browserTagColor(status)}
                style={{ fontSize: 13, padding: '4px 12px' }}
              >
                {b === 'edge' ? 'Edge' : 'Chrome'}
                {browserTagText(status)}
              </Tag>
            )
          })}
        </div>
      )}

      {/* 操作按钮 */}
      <Space wrap>
        <TipButton
          tip="从 Edge 浏览器导入 Cookie"
          type="primary"
          icon={<ImportOutlined />}
          loading={importing}
          onClick={() => onImport('edge')}
          disabled={!browserStatus?.edge?.exists}
          style={{ background: '#FF6200', borderColor: '#FF6200' }}
        >
          从 Edge 导入
        </TipButton>
        <TipButton
          tip="从 Chrome 浏览器导入 Cookie"
          icon={<ImportOutlined />}
          loading={importing}
          onClick={() => onImport('chrome')}
          disabled={!browserStatus?.chrome?.exists}
        >
          从 Chrome 导入
        </TipButton>
        <TipButton tip="在系统浏览器打开闲鱼登录页" icon={<ReloadOutlined />} onClick={onOpenBrowser}>
          打开闲鱼网页
        </TipButton>
      </Space>

      {/* 文件锁定时的解决方案 */}
      <Alert
        type="warning"
        showIcon
        message="遇到「文件被锁定」错误？"
        description={
          <div style={{ fontSize: 12, lineHeight: 1.8 }}>
            <p style={{ margin: '4px 0' }}>Edge/Chrome 运行时会锁定 Cookie 文件。如果导入失败，请尝试：</p>
            <ol style={{ margin: '4px 0 4px 20px', padding: 0 }}>
              <li>点击下方「自动关闭浏览器并导入」按钮（会自动关闭浏览器进程后重试）</li>
              <li>或手动完全关闭浏览器（包括任务栏托盘后台进程）后重试</li>
              <li>或改用「Cookie 注入」标签页，从浏览器开发者工具复制 Cookie 后粘贴</li>
            </ol>
          </div>
        }
        style={{ marginBottom: 8 }}
      />

      {/* 自动关闭浏览器并导入按钮 */}
      <Space wrap>
        <TipButton
          tip="自动关闭 Edge 后导入 Cookie"
          icon={<ThunderboltOutlined />}
          loading={importing}
          onClick={() => onImport('edge', true)}
          disabled={!browserStatus?.edge?.exists}
          danger
        >
          自动关闭 Edge 并导入
        </TipButton>
        <TipButton
          tip="自动关闭 Chrome 后导入 Cookie"
          icon={<ThunderboltOutlined />}
          loading={importing}
          onClick={() => onImport('chrome', true)}
          disabled={!browserStatus?.chrome?.exists}
          danger
        >
          自动关闭 Chrome 并导入
        </TipButton>
      </Space>

      {/* 导入结果提示（支持多行显示） */}
      {importResult && (
        <Alert
          type={importResult.includes('成功') ? 'success' : 'error'}
          message={importResult.split('\n').map((line, i) => (
            <div key={`${line}-${i}`} style={{ fontSize: 12, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{line}</div>
          ))}
          showIcon
          closable
          onClose={onClearImportResult}
        />
      )}

      <Divider plain style={{ margin: '8px 0' }}>
        <Text type="secondary">或使用其他方式</Text>
      </Divider>

      <Space>
        <TipButton tip="重新检测浏览器状态" icon={<ReloadOutlined />} onClick={onRefreshStatus}>
          刷新检测
        </TipButton>
      </Space>
    </div>
  )
}

// 登录页面：独立于 MainLayout，提供多种登录方式
export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirect = searchParams.get('redirect') || '/'
  // 主题适配：玻璃态卡片颜色、Cookie 字段标签背景等都需要跟随主题
  const { isDark } = useTheme()
  const { token: themeToken } = theme.useToken()

  // 当前登录态信息
  const [cookieInfo, setCookieInfo] = useState<SavedCookieInfo | null>(null)
  const [checkingAuth, setCheckingAuth] = useState(true)

  // Cookie 注入 Tab 状态 — 分字段输入（参考旧版 dashboard 设计）
  // COOKIE_KEYS 与 EMPTY_COOKIE_FIELDS 已提到模块级，被多个辅助函数共用
  const [cookieFields, setCookieFields] = useState<Record<string, string>>({
    _m_h5_tk: '', cookie2: '', sgcookie: '', unb: '',
  })
  const [injecting, setInjecting] = useState(false)
  const [autoFilling, setAutoFilling] = useState(false)
  const [autoFillResult, setAutoFillResult] = useState<{ text: string; error: boolean } | null>(null)

  // 快速粘贴：用户可从浏览器开发者工具全量复制 Cookie 键值对后直接粘贴
  const [pasteText, setPasteText] = useState('')
  const [parseResult, setParseResult] = useState<{
    total: number
    matched: string[]
    missing: string[]
  } | null>(null)

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

  // Cookie 教程 Modal
  const [tutorialVisible, setTutorialVisible] = useState(false)

  const pollRef = useRef(pollTimer)
  pollRef.current = pollTimer

  // 页面加载时检查当前登录态 + 填充已保存的 Cookie 值
  useEffect(() => {
    // 不再因已登录而跳转 — 用户点击「登录管理」就是为了管理 Cookie
    authApi.getMe().then(() => {
      // 仅记录状态，不跳转
    }).catch(() => {})
      .finally(() => setCheckingAuth(false))

    // 并行获取：Cookie 摘要、浏览器状态、以及已保存的具体 Cookie 值（用于返显）
    authApi.getSavedCookieInfo().then(setCookieInfo).catch(() => {})
    authApi.getBrowserImportStatus().then(setBrowserStatus).catch(() => {})

    // 自动获取已保存的 cookie 值填充到输入框（让用户看到当前值）
    fetch(`${API_BASE}api/auth/cookie/fetch-keys?keys=_m_h5_tk,cookie2,sgcookie,unb`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok && data.cookies) {
          // 复用 applyCookiesToFields：与 handleParsePaste/handleAutoFillFromBrowser 同一逻辑
          const { updated, filled } = applyCookiesToFields(data.cookies, cookieFields)
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
      // 将分字段拼接为旧版格式的 cookie 字符串（提取为 buildCookieString 降低嵌套）
      const cookieString = buildCookieString(cookieFields)
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
    setPasteText('')
    setParseResult(null)
  }

  // 解析粘贴的 Cookie 文本，提取关键键值对并填充到分字段输入框
  const handleParsePaste = (text: string) => {
    setPasteText(text)
    const trimmed = text.trim()
    if (!trimmed) {
      setParseResult(null)
      return
    }

    const parsed = parseCookieText(trimmed)
    const allKeys = Object.keys(parsed)
    if (allKeys.length === 0) {
      // S7747：map 已返回新数组，无需展开克隆
      setParseResult({ total: 0, matched: [], missing: COOKIE_KEYS.map((ck) => ck.key) })
      return
    }

    // 复用 applyCookiesToFields：与 useEffect 自动填充、handleAutoFillFromBrowser 共用同一循环
    const { updated, matched } = applyCookiesToFields(parsed, cookieFields)
    setCookieFields(updated)

    const missing = COOKIE_KEYS.map((ck) => ck.key).filter((k) => !matched.includes(k))
    setParseResult({ total: allKeys.length, matched, missing })
  }

  // 粘贴事件处理：实时解析剪贴板内容
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    // 使用剪贴板原始文本，确保解析准确性
    const text = e.clipboardData.getData('text')
    if (text) {
      e.preventDefault()
      handleParsePaste(text)
    }
  }

  // 从浏览器自动获取（填充到各字段）
  const handleAutoFillFromBrowser = async () => {
    setAutoFilling(true)
    setAutoFillResult(null)
    try {
      const r = await fetch(`${API_BASE}api/auth/cookie/fetch-keys?keys=_m_h5_tk,cookie2,sgcookie,unb`, {
        credentials: 'include',
      })
      const data = await r.json()
      if (data.ok && data.cookies) {
        // 先用空模板重置字段，再用 applyCookiesToFields 应用浏览器返回值（避免残留值干扰）
        const { updated, filled } = applyCookiesToFields(data.cookies, EMPTY_COOKIE_FIELDS)
        setCookieFields(updated)
        // Cookie 来源说明：仅对特定 source 显示（提取为 sourceLabel 降低嵌套）
        setAutoFillResult({
          text: `成功获取 ${filled} 个 Cookie 值${sourceLabel(data.source)}`,
          error: data.source === 'cookie_store_json_fallback',
        })
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
  // autoClose: 检测到文件锁定时自动关闭浏览器进程后重试
  const handleImportFromBrowser = async (browser: 'edge' | 'chrome', autoClose: boolean = false) => {
    setImporting(true)
    setImportResult(null)
    try {
      const result = await authApi.importFromBrowser(browser, autoClose)
      if (result.ok) {
        setImportResult(result.message || `成功从 ${browser} 导入 ${result.injected} 个 Cookie`)
        message.success(result.message || '导入成功')
        onLoginSuccess()
      } else {
        // 失败分支：用 formatImportResult 拼接 errMsg + hint（与 catch 分支共用）
        const errMsg = result.error || '导入失败'
        setImportResult(formatImportResult(errMsg, result.hint))
        message.error(errMsg)
      }
    } catch (err: any) {
      // catch 分支：从 axios 错误对象提取 errMsg + hint，再统一格式化
      const { errMsg, hint } = extractImportBrowserError(err)
      setImportResult(formatImportResult(errMsg, hint))
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
  // 启动期间禁用按钮 + 已存在会话时禁用，避免用户连续点击启动多次
  // （每次点击都会拉起 1 个新 Edge 进程，导致 4+ 个标签页）
  const [startingBrowser, setStartingBrowser] = useState(false)
  const handleStartBrowserLogin = async () => {
    if (startingBrowser) return
    setStartingBrowser(true)
    try {
      const result = await authApi.startBrowserLogin()
      if (result.ok) {
        setLoginStatus({
          method: 'browser',
          status: 'running',
          message: result.message || '正在启动浏览器窗口...',
          elapsed: 0,
        })
        message.info(result.message || '正在启动浏览器窗口...')
        startPolling()
      } else {
        message.error(result.error || '启动失败')
      }
    } catch (err: any) {
      message.error(err?.response?.data?.error || '请求失败')
    } finally {
      // 给后端 1 秒时间更新 _session.status=running，
      // 防止用户在按钮恢复瞬间再次点击（去抖）
      setTimeout(() => setStartingBrowser(false), 1000)
    }
  }

  // 开始轮询登录状态
  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    const stopPolling = () => {
      clearInterval(pollRef.current!)
      setPollTimer(null)
    }
    void pollLoginTick(setLoginStatus, onLoginSuccess, stopPolling)
    const timer = setInterval(() => void pollLoginTick(setLoginStatus, onLoginSuccess, stopPolling), 1000)
    setPollTimer(timer)
  }

  // 取消登录
  const handleCancelLogin = async () => {
    // 先停轮询再发 cancel 请求：
    // 否则 cancel 接口返回前，in-flight 的轮询 tick 会 resolve 并把
    // cancelled 状态写回 loginStatus，覆盖下面的 setLoginStatus(null)，
    // 导致页面卡在"已取消"状态无法回到启动按钮初始态
    if (pollRef.current) {
      clearInterval(pollRef.current)
      setPollTimer(null)
    }
    try {
      await authApi.cancelLogin()
      setLoginStatus(null)
      message.info('已取消登录')
    } catch {
      message.error('取消失败')
    }
  }

  if (checkingAuth) {
    return (
      <>
        <TidalForagers />
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          height: '100vh', position: 'relative', zIndex: 1,
        }}>
          <Spin size="large" tip="正在检查登录状态..."><div /></Spin>
        </div>
      </>
    )
  }

  const tabItems = [
    {
      key: 'browser-login',
      label: (
        <span style={{ fontWeight: 600 }}>
          <GlobalOutlined /> 浏览器登录
          <Tag color="orange" style={{ marginLeft: 6, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>推荐</Tag>
        </span>
      ),
      children: (
        <BrowserLoginTab
          loginStatus={loginStatus}
          startingBrowser={startingBrowser}
          onStart={handleStartBrowserLogin}
          onCancel={handleCancelLogin}
        />
      ),
    },
    {
      key: 'cookie-inject',
      label: (
        <span style={{ fontWeight: 500 }}><KeyOutlined /> Cookie 注入</span>
      ),
      children: (
        <CookieInjectTab
          cookieFields={cookieFields}
          setCookieFields={setCookieFields}
          injecting={injecting}
          autoFilling={autoFilling}
          autoFillResult={autoFillResult}
          pasteText={pasteText}
          parseResult={parseResult}
          cookieInfo={cookieInfo}
          onInject={handleInjectCookie}
          onAutoFill={handleAutoFillFromBrowser}
          onClear={handleClearCookies}
          onParsePaste={handleParsePaste}
          onPaste={handlePaste}
          onFileUpload={handleFileUpload}
        />
      ),
    },
    {
      key: 'browser-import',
      label: (
        <span style={{ fontWeight: 500 }}><ChromeOutlined /> 浏览器导入</span>
      ),
      children: (
        <BrowserImportTab
          browserStatus={browserStatus}
          importing={importing}
          importResult={importResult}
          onImport={handleImportFromBrowser}
          onOpenBrowser={handleOpenBrowser}
          onRefreshStatus={() => {
            authApi.getBrowserImportStatus().then(setBrowserStatus).catch(() => {})
            message.info('已刷新浏览器状态')
          }}
          onClearImportResult={() => setImportResult(null)}
        />
      ),
    },
  ]

  return (
    <>
      {/* 生成艺术背景：Tidal Foragers 鱼群流场 */}
      <TidalForagers />

      <div style={{
        display: 'flex', justifyContent: 'center', alignItems: 'center',
        minHeight: '100vh', padding: '24px 16px',
        position: 'relative', zIndex: 1,
      }}>
        <Card
          style={{
            width: '100%', maxWidth: 560,
            borderRadius: 16,
            // 玻璃态设计：随主题切换
            // - 暗色主题：半透明深色 + 模糊，文字用浅色
            // - 亮色主题：白色半透明 + 模糊 + 阴影，文字用深色
            background: isDark ? 'rgba(15, 25, 45, 0.65)' : 'rgba(255, 255, 255, 0.85)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid rgba(255, 255, 255, 0.6)',
            boxShadow: isDark
              ? '0 8px 32px rgba(0, 0, 0, 0.4)'
              : '0 8px 32px rgba(31, 119, 180, 0.15), 0 2px 8px rgba(0, 0, 0, 0.08)',
          }}
          styles={{ body: { padding: '32px 24px 24px' } }}
        >
          {/* 品牌头部 */}
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={{
              width: 64, height: 64, borderRadius: 18,
              background: 'linear-gradient(135deg, #FF6200, #FF8C00)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 12px', fontSize: 32, color: '#fff', fontWeight: 700,
              boxShadow: '0 4px 20px rgba(255, 98, 0, 0.4)',
            }}>
              闲
            </div>
            <Title level={4} style={{ margin: 0, color: themeToken.colorTextHeading, fontWeight: 600 }}>闲鱼猎人 - 登录</Title>
            <Text style={{ fontSize: 13, color: themeToken.colorTextSecondary }}>
              选择一种方式完成闲鱼账号认证
            </Text>
          </div>

          <Tabs items={tabItems} centered />

          {/* 辅助功能：获取 Cookie 教程 */}
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <TipButton
              tip="查看获取 Cookie 的图文教程"
              type="link"
              size="small"
              icon={<QuestionCircleOutlined />}
              onClick={() => setTutorialVisible(true)}
              style={{ color: themeToken.colorTextSecondary }}
            >
              如何获取 Cookie？
            </TipButton>
          </div>
        </Card>
      </div>

      {/* Cookie 教程 Modal */}
      <Modal
        title="如何获取闲鱼 Cookie"
        open={tutorialVisible}
        onCancel={() => setTutorialVisible(false)}
        footer={[
          <TipButton key="close" tip="关闭教程弹窗" onClick={() => setTutorialVisible(false)}>知道了</TipButton>,
        ]}
      >
        <div style={{ lineHeight: 1.8 }}>
          <p><strong>方法一：浏览器窗口登录（推荐）</strong></p>
          <p>切换到「浏览器登录」标签页，启动 Playwright 浏览器窗口手动登录。</p>

          <p><strong>方法二：浏览器开发者工具（Cookie 注入）</strong></p>
          <ol>
            <li>在浏览器中打开 <a href="https://www.goofish.com" target="_blank" rel="noopener noreferrer">闲鱼官网</a> 并登录</li>
            <li>按 <kbd>F12</kbd> 打开开发者工具，切换到「Application」标签</li>
            <li>左侧选择「Cookies」→ 找到 goofish.com 域名</li>
            <li><strong>方式 A（快速）</strong>：全选 Cookie 列表，右键复制后，直接粘贴到「快速粘贴 Cookie」输入框，系统会自动识别并填充关键字段</li>
            <li><strong>方式 B（手动）</strong>：分别复制以下 4 个字段的值到对应输入框：
              <ul>
                <li><code>_m_h5_tk</code>（安全令牌）</li>
                <li><code>cookie2</code>（会话ID）</li>
                <li><code>sgcookie</code>（安全Cookie）</li>
                <li><code>unb</code>（用户ID）</li>
              </ul>
            </li>
            <li>点击「注入 Cookie 登录」</li>
          </ol>

          <p><strong>方法三：浏览器导入（自动）</strong></p>
          <p>切换到「浏览器导入」标签页，系统会自动从 Edge/Chrome 提取 Cookie。</p>

          <Alert
            type="warning"
            showIcon
            message="Cookie 有效期约 30 天，过期后需重新获取"
            style={{ marginTop: 16 }}
          />
        </div>
      </Modal>
    </>
  )
}

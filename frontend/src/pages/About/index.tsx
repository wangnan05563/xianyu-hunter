import { useEffect, useState } from 'react'
import { Typography, Tooltip, theme } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import { BrandCard } from './BrandCard'
import { AboutMenuList } from './AboutMenuList'
import { OpenSourceLicenses } from './OpenSourceLicenses'
import { useUpdateChecker } from './useUpdateChecker'
import { aboutApi } from '../../api'
import { TEXTS } from './i18n'
import './about.css'

const { Text } = Typography

interface BuildInfo {
  version: string
  buildDate: string
  gitSha: string
}

// API 失败时的兜底值，确保 UI 不白屏
const FALLBACK: BuildInfo = { version: '--', buildDate: '--', gitSha: 'unknown' }

export default function About() {
  const { token } = theme.useToken()
  const [info, setInfo] = useState<BuildInfo>(FALLBACK)
  const [licensesOpen, setLicensesOpen] = useState(false)

  // 拉取元信息；失败时 FALLBACK 兜底，不阻塞 UI
  useEffect(() => {
    aboutApi.get().then(
      (d) => setInfo({ version: d.version, buildDate: d.build_date, gitSha: d.git_sha }),
      () => { /* 失败用 FALLBACK，不阻塞列表渲染 */ },
    )
  }, [])

  const { state, run, copy } = useUpdateChecker(info.version)

  // 嵌入 MainLayout 的 SheetWorkspace 内：不再渲染自有 Header/Layout/返回按钮，
  // 由 SheetWorkspace 的 sheet-content-area 提供滚动容器，标签栏提供关闭入口
  return (
    <div className="xh-about-content">
      <h1
        className="xh-about-h1"
        style={{
          fontFamily: '"Cormorant Garamond", "Noto Serif SC", Georgia, serif',
          fontSize: 40,
          fontWeight: 600,
          letterSpacing: '-0.5px',
          color: token.colorTextHeading,
          marginBottom: 8,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <InfoCircleOutlined style={{ fontSize: 28, color: token.colorPrimary }} />
        {TEXTS.h1Title}
      </h1>
      <BrandCard
        version={info.version}
        buildDate={info.buildDate}
        gitSha={info.gitSha}
        state={state}
        onCheck={run}
        onCopy={copy}
      />
      <AboutMenuList onOpenLicenses={() => setLicensesOpen(true)} />
      <OpenSourceLicenses
        open={licensesOpen}
        onClose={() => setLicensesOpen(false)}
      />
      <div className="xh-about-footer">
        <Tooltip title={TEXTS.riskDisclaimer}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            © {new Date().getFullYear()} {TEXTS.footerCopyright}
          </Text>
        </Tooltip>
      </div>
    </div>
  )
}

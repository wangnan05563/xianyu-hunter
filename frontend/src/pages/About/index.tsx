import { useEffect, useState } from 'react'
import { Typography, Tooltip } from 'antd'
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

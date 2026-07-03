import { useEffect, useState } from 'react'
import { Layout, Typography, Button, Space, Tooltip, theme } from 'antd'
import { ArrowLeftOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { BrandCard } from './BrandCard'
import { AboutMenuList } from './AboutMenuList'
import { OpenSourceLicenses } from './OpenSourceLicenses'
import { useUpdateChecker } from './useUpdateChecker'
import { aboutApi } from '../../api'
import { TEXTS } from './i18n'
import './about.css'

const { Header, Content } = Layout
const { Title, Text } = Typography

interface BuildInfo {
  version: string
  buildDate: string
  gitSha: string
}

// API 失败时的兜底值，确保 UI 不白屏
const FALLBACK: BuildInfo = { version: '--', buildDate: '--', gitSha: 'unknown' }

export default function About() {
  const navigate = useNavigate()
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

  return (
    <Layout style={{ height: '100%' }}>
      <Header
        style={{
          background: token.colorBgContainer,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0, 0, 0, 0.04)',
          flex: '0 0 auto',
          height: 56,
        }}
      >
        <Space>
          <InfoCircleOutlined style={{ fontSize: 18, color: token.colorPrimary }} />
          <Title level={4} style={{ margin: 0 }}>{TEXTS.pageTitle}</Title>
        </Space>
        <Button
          type="primary"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/')}
        >
          {TEXTS.backToConsole}
        </Button>
      </Header>
      <Content style={{ background: token.colorBgLayout, overflow: 'auto', flex: 1 }}>
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
            }}
          >
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
      </Content>
    </Layout>
  )
}

import { useState, useMemo } from 'react'
import { Modal, Input, List, Tag, Typography, theme } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { TEXTS } from './i18n'

// 首版静态依赖清单（P2 接入 license-checker 自动生成）
// 数据来源：frontend/package.json + requirements.txt
// 字段：name / version / license / repo
interface Dependency {
  name: string
  version: string
  license: string
  repo: string
}

// 前端依赖（来自 package.json dependencies + devDependencies）
const FRONTEND_DEPS: Dependency[] = [
  { name: '@ant-design/icons', version: '^5.5.0', license: 'MIT', repo: 'https://github.com/ant-design/ant-design-icons' },
  { name: '@dnd-kit/core', version: '^6.1.0', license: 'MIT', repo: 'https://github.com/clauderic/dnd-kit' },
  { name: '@dnd-kit/sortable', version: '^8.0.0', license: 'MIT', repo: 'https://github.com/clauderic/dnd-kit' },
  { name: '@dnd-kit/utilities', version: '^3.2.0', license: 'MIT', repo: 'https://github.com/clauderic/dnd-kit' },
  { name: 'antd', version: '^5.21.0', license: 'MIT', repo: 'https://github.com/ant-design/ant-design' },
  { name: 'axios', version: '^1.7.0', license: 'MIT', repo: 'https://github.com/axios/axios' },
  { name: 'dayjs', version: '^1.11.0', license: 'MIT', repo: 'https://github.com/iamkun/dayjs' },
  { name: 'echarts', version: '^5.5.0', license: 'Apache-2.0', repo: 'https://github.com/apache/echarts' },
  { name: 'echarts-for-react', version: '^3.0.2', license: 'MIT', repo: 'https://github.com/hustcc/echarts-for-react' },
  { name: 'p5', version: '^2.3.0', license: 'LGPL-2.1', repo: 'https://github.com/processing/p5.js' },
  { name: 'react', version: '^18.3.1', license: 'MIT', repo: 'https://github.com/facebook/react' },
  { name: 'react-dom', version: '^18.3.1', license: 'MIT', repo: 'https://github.com/facebook/react' },
  { name: 'react-flow-renderer', version: '^10.3.17', license: 'MIT', repo: 'https://github.com/wbkd/react-flow' },
  { name: 'react-router-dom', version: '^6.26.0', license: 'MIT', repo: 'https://github.com/remix-run/react-router' },
  { name: 'zustand', version: '^4.5.0', license: 'MIT', repo: 'https://github.com/pmndrs/zustand' },
  // devDependencies
  { name: '@testing-library/react', version: '^16.3.2', license: 'MIT', repo: 'https://github.com/testing-library/react-testing-library' },
  { name: '@vitejs/plugin-react', version: '^4.3.0', license: 'MIT', repo: 'https://github.com/vitejs/vite-plugin-react' },
  { name: 'typescript', version: '^5.5.0', license: 'Apache-2.0', repo: 'https://github.com/microsoft/TypeScript' },
  { name: 'vite', version: '^5.4.0', license: 'MIT', repo: 'https://github.com/vitejs/vite' },
  { name: 'vite-plugin-pwa', version: '^1.3.0', license: 'MIT', repo: 'https://github.com/vite-pwa/vite-plugin-pwa' },
  { name: 'vitest', version: '^4.1.9', license: 'MIT', repo: 'https://github.com/vitest-dev/vitest' },
]

// 后端依赖（来自 requirements.txt 直接依赖）
const BACKEND_DEPS: Dependency[] = [
  { name: 'fastapi', version: '0.136.3', license: 'MIT', repo: 'https://github.com/tiangolo/fastapi' },
  { name: 'uvicorn', version: '0.48.0', license: 'BSD-3-Clause', repo: 'https://github.com/encode/uvicorn' },
  { name: 'pydantic', version: '2.13.4', license: 'MIT', repo: 'https://github.com/pydantic/pydantic' },
  { name: 'pydantic-settings', version: '2.14.1', license: 'MIT', repo: 'https://github.com/pydantic/pydantic-settings' },
  { name: 'sqlalchemy', version: '2.0.50', license: 'MIT', repo: 'https://github.com/sqlalchemy/sqlalchemy' },
  { name: 'aiosqlite', version: '0.22.1', license: 'MIT', repo: 'https://github.com/omnilib/aiosqlite' },
  { name: 'playwright', version: '1.60.0', license: 'Apache-2.0', repo: 'https://github.com/microsoft/playwright-python' },
  { name: 'loguru', version: '0.7.3', license: 'MIT', repo: 'https://github.com/Delgan/loguru' },
  { name: 'httpx', version: '0.28.1', license: 'BSD-3-Clause', repo: 'https://github.com/encode/httpx' },
  { name: 'typer', version: '0.26.6', license: 'MIT', repo: 'https://github.com/tiangolo/typer' },
  { name: 'PyYAML', version: '6.0.3', license: 'MIT', repo: 'https://github.com/yaml/pyyaml' },
  { name: 'Jinja2', version: '3.1.6', license: 'BSD-3-Clause', repo: 'https://github.com/pallets/jinja' },
  { name: 'keyring', version: '25.7.0', license: 'MIT', repo: 'https://github.com/jaraco/keyring' },
  { name: 'cryptography', version: '49.0.0', license: 'Apache-2.0/BSD-3-Clause', repo: 'https://github.com/pyca/cryptography' },
  { name: 'rich', version: '15.0.0', license: 'MIT', repo: 'https://github.com/Textualize/rich' },
  { name: 'tenacity', version: '9.1.4', license: 'Apache-2.0', repo: 'https://github.com/jd/tenacity' },
  { name: 'APScheduler', version: '3.11.2', license: 'MIT', repo: 'https://github.com/agronholm/apscheduler' },
  { name: 'python-multipart', version: '0.0.30', license: 'Apache-2.0', repo: 'https://github.com/Kludex/python-multipart' },
  { name: 'starlette', version: '1.2.1', license: 'BSD-3-Clause', repo: 'https://github.com/encode/starlette' },
  { name: 'websockets', version: '16.0', license: 'BSD-3-Clause', repo: 'https://github.com/python-websockets/websockets' },
]

const ALL_DEPS: Dependency[] = [...FRONTEND_DEPS, ...BACKEND_DEPS].sort((a, b) =>
  a.name.toLowerCase().localeCompare(b.name.toLowerCase()),
)

interface OpenSourceLicensesProps {
  open: boolean
  onClose: () => void
}

export function OpenSourceLicenses({ open, onClose }: OpenSourceLicensesProps) {
  const { token } = theme.useToken()
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase()
    if (!kw) return ALL_DEPS
    return ALL_DEPS.filter(
      (d) => d.name.toLowerCase().includes(kw) || d.license.toLowerCase().includes(kw),
    )
  }, [search])

  return (
    <Modal
      title={TEXTS.licensesTitle}
      open={open}
      onCancel={onClose}
      footer={<Typography.Text type="secondary" style={{ fontSize: 12 }}>{TEXTS.licensesFooter}</Typography.Text>}
      width={720}
      destroyOnHidden
    >
      <Input
        placeholder={TEXTS.licensesSearchPlaceholder}
        prefix={<SearchOutlined />}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        allowClear
        style={{ marginBottom: 16 }}
      />
      <div style={{ maxHeight: '60vh', overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: token.colorTextSecondary }}>
            {TEXTS.emptySearch}
          </div>
        ) : (
          <List
            size="small"
            dataSource={filtered}
            renderItem={(d) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <a href={d.repo} target="_blank" rel="noopener noreferrer">
                      {d.name} <span style={{ color: token.colorTextTertiary }}>@{d.version}</span>
                    </a>
                  }
                  description={<Tag color="blue">{d.license}</Tag>}
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  )
}

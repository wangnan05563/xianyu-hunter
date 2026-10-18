import { Button, Result, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { sheetRegistry } from '../../components/SheetWorkspace/sheetRegistry'

// 未知路由的显式落点：替代过去的 <Navigate to="/" replace /> 静默回首页
// 静默跳转会让用户以为点错了菜单或程序坏了，并丢掉「访问过不存在页面」这一事实
export default function NotFound() {
  const navigate = useNavigate()
  const known = sheetRegistry.map((s) => s.path).sort()

  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="当前地址没有对应的页面，可以直接返回首页，或从下方可用页面中选择。"
      extra={
        <Button type="primary" onClick={() => navigate('/', { replace: true })}>
          返回首页
        </Button>
      }
    >
      <div style={{ marginTop: 24, textAlign: 'left' }}>
        <Typography.Text type="secondary">可用页面（{known.length}）</Typography.Text>
        <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {known.map((path) => (
            <Button key={path} size="small" onClick={() => navigate(path)}>
              {path}
            </Button>
          ))}
        </div>
      </div>
    </Result>
  )
}

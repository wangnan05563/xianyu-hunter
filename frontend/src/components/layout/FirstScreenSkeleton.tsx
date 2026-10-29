import { Layout, Skeleton } from 'antd'

const { Header, Sider, Content } = Layout

// 首屏阶段文案：三段全屏 Spin 合并成一次骨架屏后，仍要告诉用户在等什么
export type FirstScreenStage = 'auth' | 'login' | 'menu'

export const FIRST_SCREEN_STAGE_LABELS: Record<FirstScreenStage, string> = {
  auth: '正在验证登录状态…',
  login: '正在跳转登录页…',
  menu: '正在加载菜单…',
}

/**
 * 首屏骨架屏（T02560 / 2.5-10）
 *
 * 替代此前「验证登录态 → 跳登录页 → 加载菜单」三段全屏 Spin 串行：
 * 三段 Spin 高度都是 100vh 居中的一个小转圈，切换时整屏闪三次且没有任何结构预告。
 * 这里一次渲染出与真实外壳同构的骨架（Header + Sider + Content），只在底部保留阶段文案。
 */
export default function FirstScreenSkeleton({ stage }: { readonly stage: FirstScreenStage }) {
  return (
    <Layout style={{ minHeight: '100vh' }} role="status" aria-live="polite">
      <Header style={{ height: 56, lineHeight: '56px', padding: '0 24px', background: '#fff' }}>
        <Skeleton active title={{ width: 180 }} paragraph={false} />
      </Header>
      <Layout>
        <Sider width={220} theme="light" style={{ padding: '16px 12px', background: '#fff' }}>
          <Skeleton active title={{ width: 120 }} paragraph={{ rows: 7 }} />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Skeleton active paragraph={{ rows: 8 }} />
          <div style={{ marginTop: 12, fontSize: 13, color: 'rgba(0, 0, 0, 0.45)' }}>
            {FIRST_SCREEN_STAGE_LABELS[stage]}
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

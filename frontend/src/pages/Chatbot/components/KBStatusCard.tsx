import { Card, Tag, Modal, Progress, message, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { KBStatus } from '../types'
import { TipButton } from '@/components/TipButton'
import { extractApiError } from '@/utils/apiError'

interface Props {
  readonly status: KBStatus
  readonly onRebuild: (force: boolean) => Promise<void>
}

// 知识库状态卡片：展示当前版本、片段数、构建时间，支持手动重建
export function KBStatusCard({ status, onRebuild }: Props) {
  const [building, setBuilding] = useState(false)

  const handleRebuild = () => {
    Modal.confirm({
      title: '重建知识库',
      content: '重建期间对话功能将使用旧版本知识库，确定继续？',
      onOk: async () => {
        setBuilding(true)
        try {
          await onRebuild(false)
          message.success('知识库重建已启动')
        } catch (err) {
          // T02891 裁决 A：远程 embedding 且总开关关闭时后端返回带 code 的 403。
          // 写死「重建启动失败」会把「去开开关」这个可执行动作降级成一次普通故障，
          // 所以优先转述后端 detail（extractApiError 内部已处理 ai_disabled 兜底文案）。
          message.error(extractApiError(err, '重建启动失败'))
        } finally {
          setBuilding(false)
        }
      },
    })
  }

  const isBuilding = building || status.building
  const progress = status.progress
  // 失败阶段用异常状态色（红色），其他构建阶段用 active 动画
  const progressStatus = progress?.phase === 'failed' ? 'exception' : 'active'

  return (
    <Card
      title="知识库状态"
      extra={
        <TipButton
          tip="重建知识库索引（使用最新文档）"
          icon={<ReloadOutlined />}
          onClick={handleRebuild}
          loading={isBuilding}
          disabled={isBuilding}
        >
          重建
        </TipButton>
      }
    >
      <p>
        当前版本：
        <Tag color={status.current_version ? 'green' : 'default'}>
          {status.current_version?.slice(0, 8) || '未构建'}
        </Tag>
      </p>
      <p>片段数量：<strong>{status.chunk_count}</strong></p>
      <p>最后构建：{status.last_build_at || '从未构建'}</p>
      {status.status === 'corrupted' && (
        <Tag color="red">知识库损坏，需人工修复</Tag>
      )}
      {status.status === 'partial' && (
        <Tag color="orange">部分片段构建失败</Tag>
      )}
      {isBuilding && progress && (
        <div style={{ marginTop: 12 }}>
          <Progress
            percent={progress.percent}
            status={progressStatus}
          />
          {progress.message && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {progress.message}
            </Typography.Text>
          )}
        </div>
      )}
    </Card>
  )
}

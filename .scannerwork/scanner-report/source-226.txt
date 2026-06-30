import { Card, Button, Tag, Modal, Progress, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { KBStatus } from '../types'

interface Props {
  status: KBStatus
  onRebuild: (force: boolean) => Promise<void>
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
        } catch {
          message.error('重建启动失败')
        } finally {
          setBuilding(false)
        }
      },
    })
  }

  const isBuilding = building || status.building

  return (
    <Card
      title="知识库状态"
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={handleRebuild}
          loading={isBuilding}
          disabled={isBuilding}
        >
          重建
        </Button>
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
      {isBuilding && <Progress percent={100} status="active" />}
    </Card>
  )
}

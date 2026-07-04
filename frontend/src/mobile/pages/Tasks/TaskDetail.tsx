// frontend/src/mobile/pages/Tasks/TaskDetail.tsx
import { Card, Descriptions, Spin, Button } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { taskApi } from '../../../api'
import type { Task } from '../../../api/types'

export default function MobileTaskDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    taskApi.get(id).then(setTask).catch(() => {}).finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  if (!task) return <div>任务不存在</div>

  return (
    <div>
      <Button onClick={() => navigate(-1)} style={{ marginBottom: 12 }}>← 返回</Button>
      <Card title={task.name} size="small">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="关键词">{task.keyword}</Descriptions.Item>
          <Descriptions.Item label="价格区间">
            ¥{task.min_price ?? 0} ~ ¥{task.max_price ?? '不限'}
          </Descriptions.Item>
          <Descriptions.Item label="排除词">{task.exclude_words || '无'}</Descriptions.Item>
          <Descriptions.Item label="地区">{task.region || '不限'}</Descriptions.Item>
          <Descriptions.Item label="模式">{task.mode}</Descriptions.Item>
          <Descriptions.Item label="状态">{task.status}</Descriptions.Item>
          <Descriptions.Item label="Cron">{task.cron}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{task.created_at}</Descriptions.Item>
        </Descriptions>
      </Card>
      {/* 复杂字段编辑引导到 PC 端 */}
      <div style={{ textAlign: 'center', marginTop: 16, fontSize: 13, color: '#999' }}>
        完整编辑请在电脑端操作
      </div>
    </div>
  )
}

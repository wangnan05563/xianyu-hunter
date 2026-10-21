// frontend/src/mobile/pages/Tasks/TaskDetail.tsx
import { Card, Descriptions, Spin, Button, Tag } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { taskApi } from '../../../api'
import type { Task } from '../../../api/types'
import FetchFailedHint from '../../../components/FetchFailedHint'
import { taskModeLabel, taskStatusColor, taskStatusLabel } from '../../../constants/taskStatus'

// 状态/模式文案与颜色来自 constants/taskStatus（与后端 domain/task.py 同源，T02716）：
// 与任务列表页共用同一份映射，同一个值不可能再一个页面中文、另一个页面英文

export default function MobileTaskDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  // 「请求失败」不等于「任务不存在」：原先 catch 吞掉后统一渲染「任务不存在」（假回执）
  const [loadFailed, setLoadFailed] = useState(false)

  const reload = useCallback(() => {
    if (!id) return
    setLoading(true)
    setLoadFailed(false)
    taskApi.get(id)
      .then(setTask)
      .catch(() => setLoadFailed(true))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { reload() }, [reload])

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  if (loadFailed) {
    return (
      <div>
        <Button onClick={() => navigate(-1)} style={{ marginBottom: 12 }}>← 返回</Button>
        <FetchFailedHint source="任务详情" onRetry={reload} />
      </div>
    )
  }
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
          <Descriptions.Item label="模式">{taskModeLabel(task.mode)}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={taskStatusColor(task.status)}>{taskStatusLabel(task.status)}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Cron">{task.cron}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{task.created_at}</Descriptions.Item>
        </Descriptions>
      </Card>
      {/* 编辑入口：/m/tasks/:id/edit 路由早已存在但没有门（FR-G-3）；
          移动端表单覆盖关键词/名称/价格/模式/地区/排除词，cron 等仍需电脑端 */}
      <Button
        type="primary"
        block
        style={{ marginTop: 12 }}
        onClick={() => navigate(`/m/tasks/${task.id}/edit`)}
      >
        编辑任务
      </Button>
      <div style={{ textAlign: 'center', marginTop: 12, fontSize: 13, color: '#999' }}>
        调度频率（Cron）等高级字段请在电脑端修改
      </div>
    </div>
  )
}

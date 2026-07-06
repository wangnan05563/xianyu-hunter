// frontend/src/mobile/pages/Tasks/index.tsx
import { Card, Switch, Tag, Spin, Empty, App } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { taskApi } from '../../../api'
import type { Task } from '../../../api/types'
import PullToRefresh from '../../components/PullToRefresh'

export default function MobileTasks() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  const fetchTasks = useCallback(async () => {
    try {
      const data = await taskApi.list()
      setTasks(data.items)
    } catch {
      // 弱网下保留已有数据
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTasks() }, [fetchTasks])

  // 启停任务：乐观更新，失败回滚
  // 用函数式 setTasks 精确回滚单个 task，避免闭包 prev 快照过期误回滚其他 task
  // （连续快速点击场景：第二次操作闭包里的 prev 已过期，整体 setTasks(prev) 会覆盖中间变化）
  const handleToggle = async (task: Task, checked: boolean) => {
    const newStatus = checked ? 'running' : 'paused'
    setTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: newStatus } : t))
    try {
      await taskApi.control(task.id, checked ? 'resume' : 'pause')
      message.success(checked ? '已启动' : '已暂停')
    } catch {
      // 仅回滚当前 task 到操作前状态，不影响其他 task 期间发生的变化
      setTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: task.status } : t))
      message.error('操作失败')
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <PullToRefresh onRefresh={fetchTasks}>
      {tasks.length === 0 ? (
        <Empty description="暂无任务" />
      ) : (
        tasks.map((task) => {
          // 卡片整体作为可聚焦链接：键盘 Enter 跳转，回车键同样可触发
          // 为什么用 role="link" 而非 <button>：卡片内嵌 <Switch> 按钮，
          // <button> 嵌套 <button> 违反 HTML 规范；用 role="link" + tabIndex 同样可达
          const goDetail = () => navigate(`/m/tasks/${task.id}`)
          const onKeyDown = (e: React.KeyboardEvent) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              goDetail()
            }
          }
          return (
            <Card
              key={task.id}
              className="m-task-card"
              size="small"
              role="link"
              tabIndex={0}
              aria-label={`查看任务 ${task.name} 详情`}
              onClick={goDetail}
              onKeyDown={onKeyDown}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>{task.name}</div>
                  <div style={{ fontSize: 13, color: '#999' }}>{task.keyword}</div>
                  <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                    <Tag color={task.status === 'running' ? 'green' : 'default'}>
                      {task.status === 'running' ? '运行中' : '已暂停'}
                    </Tag>
                    <Tag>{task.mode === 'auto' ? '全自动' : task.mode === 'semi_auto' ? '半自动' : '确认'}</Tag>
                  </div>
                </div>
                {/* 启停开关：阻止冒泡避免触发卡片点击；按钮仍可独立键盘操作 */}
                <Switch
                  checked={task.status === 'running'}
                  onChange={(checked, e) => { e.stopPropagation(); handleToggle(task, checked) }}
                  size="small"
                />
              </div>
            </Card>
          )
        })
      )}
    </PullToRefresh>
  )
}

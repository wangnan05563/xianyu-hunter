// frontend/src/mobile/pages/TaskEditor/index.tsx
import { Card, Form, Input, InputNumber, Button, Select, Spin, App, Space } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { TASK_MODE, isTaskMode, type TaskModeValue } from '../../../constants/taskStatus'
import { useEffect, useState } from 'react'
import { taskApi } from '../../../api'
import type { Task, TaskCreateBody } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

// 安全解析字符串数组字段：后端 Task.exclude_words 是 JSON 字符串，需还原为数组供 Select tags 模式回显
const safeParseStringArray = (v: unknown): string[] => {
  if (Array.isArray(v)) return v
  if (typeof v === 'string' && v.trim()) {
    try { return JSON.parse(v) as string[] } catch { return [] }
  }
  return []
}

export default function MobileTaskEditor() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  // 编辑模式：id 存在；新建模式：id 不存在
  const isEdit = Boolean(id)
  const [form] = Form.useForm<TaskCreateBody>()
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  // mode 不在表单里（移动端没有模式选择控件），单独用 state 承载详情返回的原值：
  // antd 的 onFinish 只回传**已注册字段**，靠 values.mode 取值会永远是兜底值，
  // 于是「编辑一个 auto 任务保存后变成 notify（只通知不抢单）」——把执行模式静默改掉。
  const [mode, setMode] = useState<TaskModeValue>(TASK_MODE.NOTIFY)

  useEffect(() => {
    if (!id) return
    // 编辑模式预填表单：拉取详情后 setFieldsValue
    let cancelled = false
    taskApi.get(id)
      .then((task: Task) => {
        if (cancelled) return
        setMode(isTaskMode(task.mode) ? task.mode : TASK_MODE.NOTIFY)
        form.setFieldsValue({
          keyword: task.keyword || '',
          name: task.name || '',
          min_price: task.min_price,
          max_price: task.max_price,
          max_publish_days: task.max_publish_days,
          region: task.region,
          exclude_words: safeParseStringArray(task.exclude_words),
        })
      })
      .catch((e: unknown) => {
        // 拉取失败提示用户，但保留空表单可填写
        message.error(extractApiError(e, '加载任务详情失败'), 3)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id, form, message])

  const handleFinish = async (values: TaskCreateBody) => {
    setSaving(true)
    try {
      const body: TaskCreateBody = {
        keyword: values.keyword,
        name: values.name,
        min_price: values.min_price ?? null,
        max_price: values.max_price ?? null,
        max_publish_days: values.max_publish_days ?? null,
        mode,
        region: values.region ?? null,
        exclude_words: values.exclude_words ?? [],
      }
      if (isEdit && id) {
        await taskApi.update(id, body)
      } else {
        await taskApi.create(body)
      }
      message.success('保存成功')
      // 路径必须 /m/ 开头并带尾斜杠，跳回任务列表
      navigate('/m/tasks/')
    } catch (e) {
      message.error(extractApiError(e, '保存失败'), 3)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <Card title={isEdit ? '编辑任务' : '新建任务'} size="small">
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        initialValues={{
          exclude_words: [],
        }}
      >
        <Form.Item
          name="keyword"
          label="关键词"
          rules={[{ required: true, message: '请输入关键词' }]}
        >
          <Input placeholder="关键词（必填）" />
        </Form.Item>

        <Form.Item name="name" label="任务名">
          <Input placeholder="任务名（可选，留空用关键词）" />
        </Form.Item>

        {/* 价格区间：双列布局节省移动端垂直空间 */}
        <Space style={{ width: '100%' }} size={12}>
          <Form.Item name="min_price" label="最低价" style={{ flex: 1, marginBottom: 16 }}>
            <InputNumber placeholder="不限" min={0} max={9999999} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_price" label="最高价" style={{ flex: 1, marginBottom: 16 }}>
            <InputNumber placeholder="不限" min={0} max={9999999} style={{ width: '100%' }} />
          </Form.Item>
        </Space>

        <Form.Item name="max_publish_days" label="最大发布天数">
          <InputNumber placeholder="不限" min={1} max={3650} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item name="exclude_words" label="排除词">
          {/* mode="tags" 允许用户输入回车添加自定义词，与 PC 端一致 */}
          <Select
            mode="tags"
            placeholder="输入排除词后回车"
            tokenSeparators={[',', '，']}
            style={{ width: '100%' }}
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0 }}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Button type="primary" htmlType="submit" block loading={saving}>
              保存
            </Button>
            <Button block onClick={() => navigate(-1)}>
              取消
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  )
}

import { useEffect, useMemo, useRef } from 'react'
import { Card, Space, Tag, Button, Tooltip } from 'antd'
import { ReloadOutlined, BulbOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useParamCalculator } from '../../hooks/useParamCalculator'
import type { ParamScenario } from '../../api'
import { SuggestionList } from './SuggestionList'

// 参数计算器面板：集成 Hook 自动校验 + 渲染建议列表
//
// 用法：
//   <ParamCalculatorPanel
//     scenario="task_create"
//     fields={formData}
//     title="参数校验"
//   />
//
// 自动监听 fields 变化，防抖 150ms 后触发校验。
// 修改 fields 任一字段（包括嵌套字段）都会触发，无需手动调用。

interface ParamCalculatorPanelProps {
  /** 校验场景：task_create / task_edit / config_update */
  scenario: ParamScenario
  /** 待校验的参数对象（变化时自动触发校验） */
  fields: Record<string, unknown>
  /** 面板标题 */
  title?: string
  /** 是否默认折叠（暂未实现，预留扩展点） */
  defaultCollapsed?: boolean
  /** 是否启用紧凑模式（单 Alert 摘要） */
  compact?: boolean
  /** 是否在挂载时立即校验一次（编辑模式恢复初始建议） */
  validateOnMount?: boolean
  /** 是否显示在 Card 内（false 时无 Card 包装，直接渲染 SuggestionList） */
  bordered?: boolean
}

const SCENARIO_LABEL: Record<ParamScenario, string> = {
  task_create: '新增任务',
  task_edit: '编辑任务',
  config_update: '系统配置',
}

export function ParamCalculatorPanel({
  scenario,
  fields,
  title = '参数校验',
  compact = false,
  validateOnMount = false,
  bordered = true,
}: ParamCalculatorPanelProps) {
  const {
    suggestions,
    hasBlocking,
    isValidating,
    lastElapsedMs,
    validateTask,
    validateConfig,
    clear,
  } = useParamCalculator(scenario, { validateOnMount })

  // 字段快照：useMemo 避免父组件每次 render 都触发校验
  // 字段 JSON 序列化作为依赖，确保内容变化才触发，避免引用变化误触发
  const fieldsJson = useMemo(() => JSON.stringify(fields), [fields])

  // 上次触发校验的字段快照，避免相同内容重复请求
  const lastFieldsRef = useRef<string>('')
  const isConfig = scenario === 'config_update'

  // 监听 fields 变化触发防抖校验
  // 为什么不在 useMemo 中触发：副作用应在 effect 中执行，render 阶段保持纯函数
  useEffect(() => {
    // 首次 mount 且非 validateOnMount 时跳过（避免编辑模式一进入就请求）
    // 为什么只检查 lastFieldsRef === ''：首次 mount 的判据是 ref 未被赋值过，
    // 不需要额外比较 fieldsJson（此时 fieldsJson 必然不等于 ''，除非 fields 本身为空对象）
    if (!validateOnMount && lastFieldsRef.current === '') {
      lastFieldsRef.current = fieldsJson
      return
    }
    // 内容相同则不重复触发
    if (fieldsJson === lastFieldsRef.current) return
    lastFieldsRef.current = fieldsJson
    if (isConfig) {
      validateConfig(fields)
    } else {
      validateTask(fields)
    }
  }, [fieldsJson, isConfig, validateTask, validateConfig, validateOnMount, fields])

  // 卸载时清空建议，避免下个面板看到上个面板的旧建议
  useEffect(() => {
    return () => clear()
  }, [clear])

  const content = (
    <SuggestionList
      suggestions={suggestions}
      isValidating={isValidating}
      elapsedMs={lastElapsedMs}
      compact={compact}
      emptyText={`${SCENARIO_LABEL[scenario]}参数配置无异常`}
    />
  )

  if (!bordered) {
    return content
  }

  return (
    <Card
      size="small"
      style={{ marginTop: 16, background: 'rgba(22, 119, 255, 0.04)' }}
      title={
        <Space size={6}>
          <BulbOutlined />
          <span>{title}</span>
          <Tag color={hasBlocking ? 'red' : isValidating ? 'processing' : 'green'} style={{ fontSize: 11 }}>
            {hasBlocking ? '阻断' : isValidating ? '校验中' : '通过'}
          </Tag>
          {lastElapsedMs > 0 && (
            <Tooltip title="校验耗时（响应预算 300ms）">
              <Tag color="default" style={{ fontSize: 11 }}>
                <ThunderboltOutlined /> {lastElapsedMs}ms
              </Tag>
            </Tooltip>
          )}
        </Space>
      }
      extra={
        <Tooltip title="重新校验">
          <Button
            size="small"
            type="text"
            icon={<ReloadOutlined />}
            loading={isValidating}
            onClick={() => {
              if (isConfig) validateConfig(fields)
              else validateTask(fields)
            }}
          />
        </Tooltip>
      }
    >
      {content}
    </Card>
  )
}

export default ParamCalculatorPanel

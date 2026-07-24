import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// Mock API 模块：避免真实网络请求
const validateTaskMock = vi.fn()
const validateConfigMock = vi.fn()

vi.mock('../../api', () => ({
  paramCalculatorApi: {
    validateTask: (...args: unknown[]) => validateTaskMock(...args),
    validateConfig: (...args: unknown[]) => validateConfigMock(...args),
  },
}))

import { ParamCalculatorPanel } from '../ParamCalculator/ParamCalculatorPanel'
import type { ValidationReport } from '../../api'

function makeReport(overrides: Partial<ValidationReport> = {}): ValidationReport {
  return {
    scenario: 'task_create',
    ok: true,
    has_blocking: false,
    warning_count: 0,
    info_count: 0,
    elapsed_ms: 8,
    suggestions: [],
    ...overrides,
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  validateTaskMock.mockReset()
  validateConfigMock.mockReset()
  validateTaskMock.mockResolvedValue(makeReport())
  validateConfigMock.mockResolvedValue(makeReport({ scenario: 'config_update' }))
  // antd 在测试环境会输出 React 警告，安静化
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.useRealTimers()
})

// 工具：推进防抖 + 微任务，让校验完成
async function flushDebounce() {
  await act(async () => {
    vi.advanceTimersByTime(200)
  })
  await act(async () => {})
}

import { act } from '@testing-library/react'

describe('ParamCalculatorPanel', () => {
  describe('初始渲染', () => {
    it('默认显示无异常状态', () => {
      render(
        <ParamCalculatorPanel
          scenario="task_create"
          fields={{ keyword: 'iphone' }}
        />,
      )
      // 首次 mount 非 validateOnMount 时跳过校验，应展示默认无异常
      expect(screen.getByText('新增任务参数配置无异常')).toBeInTheDocument()
    })

    it('validateOnMount 时挂载即触发校验', async () => {
      const { container } = render(
        <ParamCalculatorPanel
          scenario="task_create"
          fields={{ keyword: 'iphone' }}
          validateOnMount
        />,
      )
      await flushDebounce()
      expect(validateTaskMock).toHaveBeenCalledTimes(1)
      // container 仅用于消除未使用变量警告
      expect(container).toBeTruthy()
    })
  })

  describe('字段变化触发校验', () => {
    it('修改字段后触发 validateTask', async () => {
      const { rerender } = render(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'a' }} />,
      )
      // 首次 mount 不校验
      expect(validateTaskMock).not.toHaveBeenCalled()

      rerender(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'b' }} />,
      )
      await flushDebounce()

      expect(validateTaskMock).toHaveBeenCalledTimes(1)
      expect(validateTaskMock).toHaveBeenCalledWith({ keyword: 'b' }, 'task_create')
    })

    it('相同字段内容不重复触发校验', async () => {
      const fields = { keyword: 'same' }
      const { rerender } = render(
        <ParamCalculatorPanel scenario="task_create" fields={fields} />,
      )
      // 强制 rerender 同样的内容
      rerender(
        <ParamCalculatorPanel scenario="task_create" fields={fields} />,
      )
      rerender(
        <ParamCalculatorPanel scenario="task_create" fields={fields} />,
      )
      await flushDebounce()
      expect(validateTaskMock).not.toHaveBeenCalled()
    })

    it('scenario=config_update 时调用 validateConfig', async () => {
      const { rerender } = render(
        <ParamCalculatorPanel scenario="config_update" fields={{ ttl: 5 }} />,
      )
      rerender(
        <ParamCalculatorPanel scenario="config_update" fields={{ ttl: 60 }} />,
      )
      await flushDebounce()

      expect(validateConfigMock).toHaveBeenCalledTimes(1)
      expect(validateConfigMock).toHaveBeenCalledWith({ ttl: 60 })
      expect(validateTaskMock).not.toHaveBeenCalled()
    })
  })

  describe('建议渲染', () => {
    it('阻断性建议时显示"阻断"状态标签', async () => {
      validateTaskMock.mockResolvedValueOnce(makeReport({
        has_blocking: true,
        suggestions: [{
          code: 'PRICE_RANGE',
          severity: 'error',
          category: 'accuracy',
          message: '价格区间无效',
          fix_hint: '检查 min_price <= max_price',
          affected_fields: ['min_price'],
        }],
      }))

      const { rerender } = render(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'a' }} />,
      )
      rerender(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'b' }} />,
      )
      await flushDebounce()

      expect(screen.getByText('阻断')).toBeInTheDocument()
      expect(screen.getByText('价格区间无效')).toBeInTheDocument()
    })

    it('校验耗时显示在标题 Tag 中', async () => {
      validateTaskMock.mockResolvedValueOnce(makeReport({ elapsed_ms: 25 }))

      const { rerender } = render(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'a' }} />,
      )
      rerender(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'b' }} />,
      )
      await flushDebounce()

      // 耗时 "25ms" 同时出现在标题 Tag 与 SuggestionList description 中，用 getAllByText 断言存在
      expect(screen.getAllByText(/25ms/).length).toBeGreaterThan(0)
    })
  })

  describe('bordered 切换', () => {
    it('bordered=false 时不渲染 Card 标题但显示建议', () => {
      render(
        <ParamCalculatorPanel
          scenario="task_create"
          fields={{ keyword: 'a' }}
          bordered={false}
          title="隐藏的标题"
        />,
      )
      // Card 不渲染 → 自定义标题不应可见
      expect(screen.queryByText('隐藏的标题')).not.toBeInTheDocument()
      // 但 SuggestionList 的空状态文案应可见
      expect(screen.getByText('新增任务参数配置无异常')).toBeInTheDocument()
    })

    it('bordered=true (默认) 渲染 Card 与标题', () => {
      render(
        <ParamCalculatorPanel
          scenario="task_create"
          fields={{ keyword: 'a' }}
          title="自定义校验标题"
        />,
      )
      expect(screen.getByText('自定义校验标题')).toBeInTheDocument()
    })
  })

  describe('重新校验按钮', () => {
    it('点击 reload 按钮触发一次新的校验', async () => {
      render(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'a' }} />,
      )
      // 点击重新校验
      const reloadButton = screen.getByRole('button')
      await act(async () => {
        fireEvent.click(reloadButton)
      })
      await flushDebounce()

      // 至少调用过一次（reload 触发）
      expect(validateTaskMock).toHaveBeenCalled()
    })
  })

  describe('卸载清理', () => {
    it('卸载后不再触发 API 调用（防抖被清理）', async () => {
      const { rerender, unmount } = render(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'a' }} />,
      )
      // 修改字段触发防抖
      rerender(
        <ParamCalculatorPanel scenario="task_create" fields={{ keyword: 'b' }} />,
      )
      // 防抖未结束就卸载
      unmount()
      await act(async () => {
        vi.advanceTimersByTime(300)
      })
      expect(validateTaskMock).not.toHaveBeenCalled()
    })
  })
})

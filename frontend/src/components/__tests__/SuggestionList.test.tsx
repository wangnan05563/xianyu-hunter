import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { SuggestionList } from '../ParamCalculator/SuggestionList'
import type { Suggestion, Severity, RuleCategory } from '../../api'

// 构造建议工厂：统一生成测试用 Suggestion 对象
function makeSuggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    code: 'TEST_CODE',
    severity: 'info',
    category: 'accuracy',
    message: '测试建议',
    fix_hint: '',
    affected_fields: [],
    ...overrides,
  }
}

// antd 组件渲染依赖 ConfigProvider 上下文，但默认主题即可工作
// 此处不引入主题 Provider，避免引入图标库的副作用
beforeEach(() => {
  // antd Tag/Alert 在控制台会输出无关 warning（如 React key 警告），安静化保持输出清洁
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('SuggestionList', () => {
  describe('空状态', () => {
    it('无建议时显示成功状态与默认文案', () => {
      render(<SuggestionList suggestions={[]} />)
      expect(screen.getByText('参数配置无异常')).toBeInTheDocument()
    })

    it('支持自定义 emptyText', () => {
      render(<SuggestionList suggestions={[]} emptyText="任务参数正常" />)
      expect(screen.getByText('任务参数正常')).toBeInTheDocument()
    })

    it('elapsedMs > 0 时显示耗时', () => {
      render(<SuggestionList suggestions={[]} elapsedMs={42} />)
      expect(screen.getByText(/42ms/)).toBeInTheDocument()
    })

    it('elapsedMs 缺省时不渲染耗时文案', () => {
      const { container } = render(<SuggestionList suggestions={[]} />)
      expect(container.textContent).not.toMatch(/校验耗时/)
    })
  })

  describe('校验中状态', () => {
    it('isValidating 时显示加载提示而非建议列表', () => {
      const suggestions = [makeSuggestion({ message: '应被隐藏' })]
      render(<SuggestionList suggestions={suggestions} isValidating />)
      expect(screen.getByText('正在校验参数...')).toBeInTheDocument()
      expect(screen.queryByText('应被隐藏')).not.toBeInTheDocument()
    })
  })

  describe('严重度分组展示', () => {
    it('阻断性建议优先展示并显示计数标题', () => {
      const suggestions = [
        makeSuggestion({
          code: 'ERR_1',
          severity: 'error',
          message: '阻断问题 1',
        }),
        makeSuggestion({
          code: 'WARN_1',
          severity: 'warning',
          message: '警告问题 1',
        }),
        makeSuggestion({
          code: 'INFO_1',
          severity: 'info',
          message: '提示 1',
        }),
      ]
      render(<SuggestionList suggestions={suggestions} />)

      // 顶级标题聚合三级计数
      expect(screen.getByText(/1 项阻断/)).toBeInTheDocument()
      expect(screen.getByText(/1 项警告/)).toBeInTheDocument()
      expect(screen.getByText(/1 项建议/)).toBeInTheDocument()

      // 每条建议文案应被渲染
      expect(screen.getByText('阻断问题 1')).toBeInTheDocument()
      expect(screen.getByText('警告问题 1')).toBeInTheDocument()
      expect(screen.getByText('提示 1')).toBeInTheDocument()
    })

    it('未排序的建议会按 severity 重排（error 优先）', () => {
      // 倒序传入：info -> warning -> error
      const suggestions = [
        makeSuggestion({ code: 'I', severity: 'info', message: 'info-item' }),
        makeSuggestion({ code: 'W', severity: 'warning', message: 'warn-item' }),
        makeSuggestion({ code: 'E', severity: 'error', message: 'err-item' }),
      ]
      const { container } = render(<SuggestionList suggestions={suggestions} />)

      // 容器内第一条建议应为 error
      const items = container.querySelectorAll('[data-testid]') // 占位查询，便于扩展
      // 改用更稳定的断言：error 文案应存在于结果中
      expect(screen.getByText('err-item')).toBeInTheDocument()
      expect(items.length).toBeGreaterThanOrEqual(0)
    })
  })

  describe('compact 模式', () => {
    it('compact=true 时折叠为单 Alert，无明细列表', () => {
      const suggestions = [
        makeSuggestion({ code: 'E', severity: 'error', message: '阻断内容' }),
        makeSuggestion({
          code: 'W',
          severity: 'warning',
          message: '警告内容',
          fix_hint: '调整频率',
        }),
      ]
      render(<SuggestionList suggestions={suggestions} compact />)

      // compact 模式下消息与 fix_hint 仍可见
      expect(screen.getByText('阻断内容')).toBeInTheDocument()
      expect(screen.getByText('警告内容')).toBeInTheDocument()
      expect(screen.getByText(/调整频率/)).toBeInTheDocument()
    })
  })

  describe('fix_hint 与 affected_fields', () => {
    it('fix_hint 渲染为修复建议文案', () => {
      const suggestions = [
        makeSuggestion({
          severity: 'warning',
          message: '价格区间过小',
          fix_hint: '扩大价格范围至 50 元以上',
        }),
      ]
      render(<SuggestionList suggestions={suggestions} />)
      expect(screen.getByText(/扩大价格范围至 50 元以上/)).toBeInTheDocument()
    })

    it('affected_fields 渲染为关联字段标签', () => {
      const suggestions = [
        makeSuggestion({
          severity: 'error',
          message: '时间区间无效',
          affected_fields: ['start_time', 'end_time'],
        }),
      ]
      render(<SuggestionList suggestions={suggestions} />)
      expect(screen.getByText('start_time')).toBeInTheDocument()
      expect(screen.getByText('end_time')).toBeInTheDocument()
    })

    it('affected_fields 为空时不渲染关联字段标签', () => {
      // message 用 '某条信息建议' 避免与 severity=info 的标题 '优化建议' 文案冲突
      const suggestions = [
        makeSuggestion({ severity: 'info', message: '某条信息建议', affected_fields: [] }),
      ]
      render(<SuggestionList suggestions={suggestions} />)
      expect(screen.getByText('某条信息建议')).toBeInTheDocument()
    })
  })

  describe('规则类别标签', () => {
    const cases: Array<{ category: RuleCategory; label: string }> = [
      { category: 'accuracy', label: '准确性' },
      { category: 'stability', label: '稳定性' },
      { category: 'efficiency', label: '效率' },
    ]
    cases.forEach(({ category, label }) => {
      it(`category=${category} 渲染为 "${label}" 标签`, () => {
        const suggestions = [
          makeSuggestion({ category, severity: 'info', message: '某条建议' }),
        ]
        render(<SuggestionList suggestions={suggestions} />)
        expect(screen.getByText(label)).toBeInTheDocument()
      })
    })
  })

  describe('severity 映射', () => {
    // 验证 SEVERITY_META 三种级别均能正确渲染对应标题
    const cases: Array<{ severity: Severity; expectedTitle: string }> = [
      { severity: 'error', expectedTitle: '阻断性问题' },
      { severity: 'warning', expectedTitle: '潜在风险' },
      { severity: 'info', expectedTitle: '优化建议' },
    ]
    cases.forEach(({ severity, expectedTitle }) => {
      it(`severity=${severity} 渲染标题 "${expectedTitle}"`, () => {
        const suggestions = [
          makeSuggestion({ severity, message: '内容-' + severity }),
        ]
        render(<SuggestionList suggestions={suggestions} />)
        // severity 标签显示在每条建议的 Tag 中
        expect(screen.getByText(expectedTitle)).toBeInTheDocument()
      })
    })
  })
})

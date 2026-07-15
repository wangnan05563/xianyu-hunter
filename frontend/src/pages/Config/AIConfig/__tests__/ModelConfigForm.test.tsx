import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import ModelConfigForm from '../components/ModelConfigForm'

test('保存配置按钮可独立持久化文本解析模型', async () => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
  const onSaveConfig = vi.fn()
  render(
    <ModelConfigForm
      config={{
        ai_enabled: true,
        base_url: 'https://api.openai.com/v1',
        api_key: '****1234',
        model: 'gpt-4.1-mini',
        vision_model: 'gpt-4o',
      }}
      onConfigChange={vi.fn()}
      showApiKey={false}
      onToggleShowApiKey={vi.fn()}
      onApplyPreset={vi.fn()}
      saving={false}
      testing={false}
      testResult={null}
      onSaveConfig={onSaveConfig}
      onTestConnection={vi.fn()}
    />,
  )

  await userEvent.click(screen.getByRole('button', { name: '保存配置' }))

  expect(onSaveConfig).toHaveBeenCalledOnce()
})

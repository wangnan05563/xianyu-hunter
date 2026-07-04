import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TabBar from '../components/TabBar'

function renderWithRouter(initialPath: string = '/m') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <TabBar />
    </MemoryRouter>
  )
}

describe('TabBar', () => {
  it('应渲染 5 个 Tab', () => {
    renderWithRouter('/m')
    expect(screen.getByText('仪表盘')).toBeInTheDocument()
    expect(screen.getByText('任务')).toBeInTheDocument()
    expect(screen.getByText('抢单')).toBeInTheDocument()
    expect(screen.getByText('客服')).toBeInTheDocument()
    expect(screen.getByText('我的')).toBeInTheDocument()
  })

  it('当前路径 /m/tasks 时任务 Tab 应为 active', () => {
    renderWithRouter('/m/tasks')
    const tasksTab = screen.getByText('任务').closest('.m-tab-item')
    expect(tasksTab).toHaveClass('active')
  })
})

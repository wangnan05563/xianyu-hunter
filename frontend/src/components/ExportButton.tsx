import { Button, Dropdown, message, Tooltip } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { exportApi, type ExportDataset, type ExportParams } from '../api'

interface ExportButtonProps {
  /** 默认导出的数据集（点击按钮直接导出此数据集） */
  dataset: ExportDataset
  /** 导出参数（task_id / start / end / status / level） */
  params?: ExportParams
  /** 按钮文字（默认"导出 CSV"） */
  label?: string
  /** 按钮大小（默认 small） */
  size?: 'small' | 'middle' | 'large'
  /** 是否显示下拉菜单（默认 true，允许切换其他数据集）
   * 设为 false 时仅导出当前数据集，无下拉
   */
  withMenu?: boolean
}

/**
 * 数据导出按钮（O-05-26）
 *
 * 设计要点：
 * - 默认点击导出当前 dataset，下拉菜单可切换其他数据集
 * - 通过 exportApi.download() 触发浏览器原生下载，避免 blob 内存
 * - 同源请求自动携带 xh_token cookie，无需额外 header
 * - 导出前给用户即时反馈（message.success），避免点击无反应
 */
export function ExportButton({
  dataset,
  params = {},
  label = '导出 CSV',
  size = 'small',
  withMenu = true,
}: ExportButtonProps) {
  const handleExport = (ds: ExportDataset) => {
    try {
      exportApi.download(ds, params)
      message.success(`正在导出 ${ds} 数据...`)
    } catch {
      message.error('导出失败，请稍后重试')
    }
  }

  // 不带下拉菜单：单按钮直接导出
  if (!withMenu) {
    return (
      <Tooltip title={`导出 ${dataset} 为 CSV（Excel 友好）`}>
        <Button size={size} icon={<DownloadOutlined />} onClick={() => handleExport(dataset)}>
          {label}
        </Button>
      </Tooltip>
    )
  }

  // 带下拉菜单：主按钮导出当前数据集，下拉可切换其他
  const menuItems: MenuProps['items'] = [
    { key: 'items', label: '商品列表' },
    { key: 'evaluations', label: '评估记录' },
    { key: 'orders', label: '订单记录' },
    { key: 'events', label: '事件日志' },
  ].filter((item) => item.key !== dataset) as MenuProps['items']

  const menu: MenuProps = {
    items: menuItems,
    onClick: ({ key }) => handleExport(key as ExportDataset),
  }

  return (
    <Dropdown.Button
      size={size}
      icon={<DownloadOutlined />}
      onClick={() => handleExport(dataset)}
      menu={menu}
    >
      {label}
    </Dropdown.Button>
  )
}

import { useState } from 'react'
import { Dropdown, message } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { exportApi, type ExportDataset, type ExportParams } from '../api'
import { notifyExportResult } from '@/utils/exportFeedback'
import { TipButton } from '@/components/TipButton'

interface ExportButtonProps {
  /** 默认导出的数据集（点击按钮直接导出此数据集） */
  readonly dataset: ExportDataset
  /** 导出参数（task_id / start / end / status / level） */
  readonly params?: ExportParams
  /** 按钮文字（默认"导出 CSV"） */
  readonly label?: string
  /** 按钮大小（默认 small） */
  readonly size?: 'small' | 'middle' | 'large'
  /** 是否显示下拉菜单（默认 true，允许切换其他数据集）
   * 设为 false 时仅导出当前数据集，无下拉
   */
  readonly withMenu?: boolean
}

/**
 * 数据导出按钮（O-05-26）
 *
 * 设计要点：
 * - 默认点击导出当前 dataset，下拉菜单可切换其他数据集
 * - 走 exportApi.downloadFile（axios blob + 隐藏 <a>）：HTTP 错误可见且不跳页
 * - 提示按实际行数给口径，0 行只出 warning，不再一律「正在导出」
 */
export function ExportButton({
  dataset,
  params = {},
  label = '导出 CSV',
  size = 'small',
  withMenu = true,
}: ExportButtonProps) {
  const [busy, setBusy] = useState(false)

  const handleExport = async (ds: ExportDataset) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await exportApi.downloadFile(ds, params)
      notifyExportResult(message, res, ds)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  // 不带下拉菜单：单按钮直接导出
  if (!withMenu) {
    return (
      <TipButton
        tip={`导出 ${dataset} 为 CSV（Excel 友好）`}
        size={size}
        icon={<DownloadOutlined />}
        loading={busy}
        onClick={() => void handleExport(dataset)}
      >
        {label}
      </TipButton>
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
    onClick: ({ key }) => void handleExport(key as ExportDataset),
  }

  return (
    <Dropdown.Button
      size={size}
      icon={<DownloadOutlined />}
      loading={busy}
      onClick={() => void handleExport(dataset)}
      menu={menu}
    >
      {label}
    </Dropdown.Button>
  )
}

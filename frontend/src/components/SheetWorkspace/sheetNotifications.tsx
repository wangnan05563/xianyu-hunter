import { notification } from 'antd'
import { useSheetStore } from '../../stores/sheetStore'
import { TipButton } from '@/components/TipButton'

/**
 * 带通知的 openSheet 包装函数
 *
 * 调用 store.openSheet 后检查返回值：
 * - 若包含 replacedSheet（循环替换触发），发右下角 Notification + 「撤销」按钮
 * - 否则静默调用，与原 openSheet 行为一致
 *
 * 为什么用右下角而非右上角（T02561 / N19）：
 * - 这两条通知是持续 5 秒的信息型提示，右上角会与 Header 右侧 7 个按钮 + 账号切换器 +
 *   用户菜单整排叠在一起，用户点不到也被遮住；右下角没有常驻控件，不遮挡任何入口。
 *
 * 为什么要包装而非在 store 内部发通知：
 * - store 是纯逻辑层，不应依赖 antd message/notification（避免引入 UI 副作用）
 * - 通知策略可能演进（如换成 Snackbar），调用方集中处方便维护
 *
 * 为什么用 notification 而非 message：
 * - antd v5 message 不支持 btn 字段，无法嵌入撤销按钮
 * - notification 支持 btn + 5 秒自动关闭，更符合"带操作的通知"语义
 *
 * 为什么 5 秒兜底：
 * - 循环替换属于"需要稍长时间决策"的操作
 * - 5 秒足够用户读完标题并决定是否撤销
 * - 不持久化：超过 5 秒用户未操作视为接受替换结果
 */
export function openSheetWithNotification(path: string) {
  const result = useSheetStore.getState().openSheet(path)
  // 路径未注册（菜单项指向没有实现的页面）时必须出声，否则用户看到的是「点了没反应」
  if (!result.ok && result.reason === 'not_found') {
    notification.warning({
      key: `sheet-not-found-${path}`,
      message: '页面不存在',
      description: `菜单指向的 ${path} 没有已实现的页面，请联系开发者或在「菜单管理」中隐藏该项`,
      duration: 5,
      placement: 'bottomRight',
    })
  }
  if (result.replacedSheet) {    const { id, title } = result.replacedSheet
    const { maxSheets } = useSheetStore.getState().preferences
    const key = `sheet-replaced-${id}`
    notification.info({
      key,
      message: '已自动替换 sheet',
      // 把上限与常驻入口写进正文：5 秒 Toast 一过就没线索，用户需要知道去哪找回（FR-B-7）
      description: `已达 ${maxSheets} 个上限，最旧非激活 sheet「${title}」被自动淘汰；可点右侧「撤销」恢复，或随时在「Sheet 偏好」的回收栈里查看`,
      duration: 5,
      placement: 'bottomRight',
      // 撤销按钮：点击后调用 restoreReplaced 从回收栈恢复被替换的 sheet
      btn: (
        <TipButton
          tip="恢复被自动替换的 sheet"
          type="primary"
          size="small"
          onClick={() => {
            useSheetStore.getState().restoreReplaced(id)
            notification.destroy(key)
          }}
        >
          撤销
        </TipButton>
      ),
    })
  }
  return result
}

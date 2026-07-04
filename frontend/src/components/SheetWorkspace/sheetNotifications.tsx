import { notification, Button } from 'antd'
import { useSheetStore } from '../../stores/sheetStore'

/**
 * 带通知的 openSheet 包装函数
 *
 * 调用 store.openSheet 后检查返回值：
 * - 若包含 replacedSheet（循环替换触发），发右上角 Notification + 「撤销」按钮
 * - 否则静默调用，与原 openSheet 行为一致
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
  if (result.replacedSheet) {
    const { id, title } = result.replacedSheet
    const key = `sheet-replaced-${id}`
    notification.info({
      key,
      message: '已自动替换 sheet',
      description: `最旧非激活 sheet「${title}」被自动淘汰，可点击右侧按钮恢复`,
      duration: 5,
      placement: 'topRight',
      // 撤销按钮：点击后调用 restoreReplaced 从回收栈恢复被替换的 sheet
      btn: (
        <Button
          type="primary"
          size="small"
          onClick={() => {
            useSheetStore.getState().restoreReplaced(id)
            notification.destroy(key)
          }}
        >
          撤销
        </Button>
      ),
    })
  }
  return result
}

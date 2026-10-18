import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 侧边栏分组展开态（深链定位，T02559 / 2.4）
 *
 * 规则：首屏按当前路由展开所属分组，用户手动开合后完全交给用户，
 * 路由变化不再联动（否则 sheet 切换时会有 SubMenu 动画遮挡内容）。
 *
 * 为什么不能只写 `useState(autoOpenKeys)`：菜单是 GET /api/menu 异步拉回来的，
 * 首帧菜单为空 → autoOpenKeys 恒为 []，useState 只认一次初值，
 * 深链直接打开 /config/ai 这类「分组内页面」时分组永远不展开、当前项也看不见。
 */
export function useOpenKeysOnDeepLink(
  autoOpenKeys: string[],
  menusReady: boolean,
): { openKeys: string[]; setOpenKeys: (keys: string[]) => void } {
  const [openKeys, setOpenKeys] = useState<string[]>(autoOpenKeys)
  const touched = useRef(false)
  const inited = useRef(autoOpenKeys.length > 0)

  const handleChange = useCallback((keys: string[]): void => {
    touched.current = true
    setOpenKeys(keys)
  }, [])

  useEffect(() => {
    if (inited.current || touched.current || !menusReady) return
    inited.current = true
    setOpenKeys(autoOpenKeys)
  }, [autoOpenKeys, menusReady])

  return { openKeys, setOpenKeys: handleChange }
}

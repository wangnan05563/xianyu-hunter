/**
 * 实时模式（liveMode）的说明文案单一事实源 —— T02659
 *
 * 为什么独立成模块而不是写死在 ItemList.tsx 里：
 * 这三段文案的共同点是「必须与代码真实行为一致」，而最容易犯的错是照着想当然写
 * ——比如建议稿里的「需持久化请改用刷新写库」。实际 `handleRefresh` 在实时模式下
 * 是 `if (liveMode) { loadLive(); return }`：只做又一次实时搜索，根本不写库。
 * 文案放进模块后可以用单测钉住口径，改行为时同步改文案，不至于悄悄说谎。
 */

/** 列表上方的一次性说明条正文 */
export const LIVE_MODE_NOTICE =
  '实时模式：这批结果只存在于本页会话、未入库，所以不分页、单条删除不可用；' +
  '地区/品牌候选也取自本次搜索结果，不是数据库全量。'

/** 说明条上的出口动作 */
export const EXIT_LIVE_MODE_LABEL = '退出实时模式'

/** 出口动作的悬浮提示：点下去会恢复什么 */
export const EXIT_LIVE_MODE_TIP = '退回数据库模式：恢复分页与删除，数据来自已入库的商品'

/**
 * 地区/品牌下拉的候选口径说明。
 * 与 regionOptions/brandOptions 的取数来源逐字对齐：
 * 实时模式 = 本次搜索原始结果提取；DB 模式 = 后端 facets 全量 DISTINCT（空则回落当前页）。
 */
export function facetTip(liveMode: boolean, kind: 'region' | 'brand'): string {
  const field = kind === 'region' ? '地区' : '品牌'
  return liveMode
    ? `实时模式：候选取自本次搜索结果的${field}，没入库的那批不在其中`
    : `数据库模式：候选来自后端 facets 的全量去重，不只当前页`
}

/**
 * 删除按钮的悬浮提示。三种禁用/可用态分开说，其中两种是「点了也没用」：
 * 实时模式（结果未入库，没有关联行可删）与 `link_id` 缺失（还没有关联记录）。
 */
export function deleteTip(opts: { liveMode: boolean; hasLinkId: boolean }): string {
  if (opts.liveMode) return '实时模式的结果未入库，没有可删除的关联记录；退出实时模式后才能删'
  if (!opts.hasLinkId) return '该商品还没有关联记录，无删除对象'
  return '删除此商品关联（不可恢复）'
}

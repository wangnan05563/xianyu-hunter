// g+X 全局快捷键键位表（T02558 / N4 重排）
// 键位按「页面英文含义首字母」取助记（d=dashboard、i=items、o=orders、e=evaluations…），
// 两处例外由 PRD 指定：m→/timeline（时间线）、b→/chatbot（bot），
// 旧表 i 指向 /timeline 且 m 指向 /chatbot，与页面名对不上、也无法靠键位记忆。
export const G_PREFIX_MAP: Record<string, string> = {
  d: '/',
  t: '/tasks',
  i: '/items',
  o: '/orders',
  e: '/evaluations',
  m: '/timeline',
  p: '/price-dashboard',
  c: '/config/price',
  l: '/logs',
  n: '/notifications',
  b: '/chatbot',
  a: '/about',
}

// 命令面板每行右侧的键位提示用（path → 'g+x'）：一个路径只对应一个键，反向表无冲突
const HINT_BY_PATH: Readonly<Record<string, string>> = Object.fromEntries(
  Object.entries(G_PREFIX_MAP).map(([key, path]) => [path, `g+${key}`]),
)

export function shortcutHintForPath(path: string): string | undefined {
  return HINT_BY_PATH[path]
}

// 面板底部说明：此前 g+X 快捷键完全不可发现（只在帮助文档里），键位重排后必须可见
export const G_PREFIX_HINT = '按 g 再按字母可快速跳转'

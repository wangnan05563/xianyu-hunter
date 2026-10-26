import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

// T02850：两条单源守卫（orderStatusSingleSource / taskStatusSingleSource）共用的一份「字面值扫描」。
//
// 为什么不能全站扫字符串：`'failed'` / `'running'` / `'error'` / `'auto'` 这些词在站内同时属于
// 批量刷新引擎、下载器、隧道、聊天消息、登录轮询、导览自动播放、评估分档等**各自的词表**。
// 实测按位扫出 10 个文件 30 处外来用法，无脑扩棘轮会把它们全判成漂移，
// 于是「豁免」被写成一句注释——下次有人加裸串照样过。这里把豁免落成**可校验的数据**：
// 每个豁免文件声明自己属于哪个域、允许哪些值，登记过期（那个词已经不在文件里）也会红。
//
// 扫描只认「值被当成状态/模式用」的位置，不认任意字符串出现：
//   x.status === 'running' / case 'paused' / { value: 'auto' }
// 类型声明里的联合（`status: 'a' | 'b'`）不在其列，那是契约定义处，本来就该写字面值。

export type ForeignVocab = {
  /** 相对 frontend/src 的路径 */
  readonly file: string
  /** 这个词表属于哪个域，写在报错信息里，便于下一轮判断该不该收口 */
  readonly domain: string
  /** 该文件允许继续裸写的取值（必须逐字出现在文件里，否则视为过期登记） */
  readonly values: readonly string[]
}

export const FOREIGN_VOCAB: readonly ForeignVocab[] = [
  {
    file: 'pages/Maintenance/BatchRefresh.tsx',
    domain: '批量刷新引擎状态与执行记录筛选（idle/running/paused/stopping/cancelled/failed）',
    values: ['running', 'paused', 'stopping', 'error', 'cancelled', 'failed'],
  },
  {
    file: 'mobile/pages/BatchRefresh/index.tsx',
    domain: '同上，移动端复用批量刷新引擎状态',
    values: ['idle', 'running', 'paused'],
  },
  {
    file: 'pages/Maintenance/Tunnel.tsx',
    domain: 'Cloudflare 隧道运行状态与操作结果（api/tunnel.ts 的契约词表）',
    values: ['running', 'failed'],
  },
  {
    file: 'pages/Orders/ItemSummaryCell.tsx',
    domain: '商品快照 Popover 的本地请求态（idle/loading/ready/failed），不是订单状态',
    values: ['failed'],
  },
  {
    file: 'pages/Maintenance/DatabaseAdmin.tsx',
    domain: '级联预览的请求态（loading/ready/error），不是任务状态',
    values: ['error'],
  },
  {
    file: 'pages/About/useUpdateChecker.ts',
    domain: '更新下载/安装状态（done/error 等）',
    values: ['error'],
  },
  {
    file: 'pages/About/BrandCard.tsx',
    domain: '同上，关于页展示下载状态',
    values: ['error'],
  },
  {
    file: 'pages/Chatbot/index.tsx',
    domain: '聊天消息发送态（pages/Chatbot/types.ts 的 sending/sent/failed）',
    values: ['failed'],
  },
  {
    file: 'pages/Login/index.tsx',
    domain: '登录轮询态（api/tunnel.ts 的 waiting/success/failed/idle + running/cancelled/timeout）',
    values: ['running'],
  },
  {
    file: 'guides/GuideController.tsx',
    domain: '导览自动播放开关 mode=auto，与任务执行模式无关',
    values: ['auto'],
  },
  {
    file: 'components/layout/UserMenu.tsx',
    domain: '昵称同步状态 nick_sync_state（ok/failed/never）',
    values: ['failed'],
  },
  {
    file: 'mobile/pages/Evaluations/index.tsx',
    domain: '评估结果分档 auto/pass/fail/insufficient（「auto」= 可抢，不是任务模式）',
    values: ['auto'],
  },
]

export type Hit = { readonly file: string; readonly line: number; readonly value: string; readonly text: string }

const SRC_ROOT = resolve(__dirname, '../..')

const IDENT = String.raw`[\w.?\[\]()]*?`

/** 「值被当成状态/模式使用」的三种位置，按取值逐个建式，便于报错时指出是哪个值 */
function positionPattern(value: string): RegExp {
  return new RegExp(
    `(?:${IDENT}(?:status|state|mode)\\s*[!=]==?\\s*'${value}')` +
      `|(?:case\\s+'${value}')` +
      `|(?:\\bvalue:\\s*'${value}')`,
  )
}

function walk(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      // 常量表本身是唯一定义处；测试里含被禁字面量会自匹配，也跳过
      if (entry.name === '__tests__' || entry.name === 'constants') continue
      out.push(...walk(join(dir, entry.name)))
    } else if (/\.tsx?$/.test(entry.name)) {
      out.push(join(dir, entry.name))
    }
  }
  return out
}

/**
 * 只保留代码行：注释里出现 `'running'` 是在解释行为，不是把取值写进运行时位置。
 * 不收口这条口径的话，`// 仅 status==='running' 任务参与倒计时` 会被当成裸写，
 * 于是「把注释改个说法」成了通过守卫的办法——那比守卫本身更糟。
 * 位置扫描与逐文件禁令共用同一个判据，两边不会因为注释松紧不同而互相打脸。
 */
export function codeLines(src: string): string[] {
  return src.split(/\r?\n/).filter((line) => {
    const t = line.trimStart()
    return !(t.startsWith('//') || t.startsWith('*') || t.startsWith('/*') || t.startsWith('*/'))
  })
}

/** 扫描全站，返回「把某个取值写在状态/模式位置上」的命中（file 相对 src） */
export function scanStatusLiteralPositions(values: readonly string[]): Hit[] {
  const patterns = values.map((value) => [value, positionPattern(value)] as const)
  const hits: Hit[] = []
  for (const path of walk(SRC_ROOT)) {
    const rel = path.slice(SRC_ROOT.length + 1).replace(/\\/g, '/')
    readFileSync(path, 'utf-8').split(/\r?\n/).forEach((line, i) => {
      if (/^\s*(\/\/|\*|\/?\*\/)/.test(line)) return // 注释不计，见 codeLines
      for (const [value, pat] of patterns) {
        if (pat.test(line)) hits.push({ file: rel, line: i + 1, value, text: line.trim().slice(0, 90) })
      }
    })
  }
  return hits
}

export function srcOf(rel: string): string {
  return readFileSync(resolve(SRC_ROOT, rel), 'utf-8')
}

/** 全站源文件（已排除 __tests__ 与 constants），供「按域定制」的扫描规则复用 */
export function listSrcFiles(): string[] {
  return walk(SRC_ROOT).map((p) => p.slice(SRC_ROOT.length + 1).replace(/\\/g, '/'))
}

export function exists(rel: string): boolean {
  return existsSync(resolve(SRC_ROOT, rel))
}

export function vocabFor(rel: string): ForeignVocab | undefined {
  return FOREIGN_VOCAB.find((v) => v.file === rel)
}

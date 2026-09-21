/**
 * 全站菜单引导配置数据 —— 单一事实源
 *
 * 为什么独立文件维护而非散落各页面：引导步骤与菜单结构绑定，
 * 集中一处便于维护、测试遍历校验、常驻按钮按 route 查表。
 *
 * 选择器约定：
 * - 所有业务页面统一使用 .page-container 作为主体容器（已由 22 个页面验证），
 *   故每个引导流程第一条务必覆盖该容器，保证至少有一个可高亮目标。
 * - 深层区块（如 .quick-entry-card）仅在确认存在时使用；GuideController 对
 *   selector 找不到的元素做容错降级（居中展示），不会导致崩溃。
 *
 * 文案来源：与 pages/Help 文档的模块说明保持一致，避免文档与引导措辞漂移。
 */
import type { MenuGuide } from './types'

export const MENU_GUIDES: MenuGuide[] = [
  {
    route: '/',
    steps: [
      { selector: '.page-container', title: '仪表盘', description: '系统总览入口，集中展示关键指标、告警、事件流与价格分布，日常运维首选首页。' },
      { selector: '.quick-entry-card', title: '可视化配置入口', description: '卡片墙统一直达高频配置页（任务、价格、评估、通知等），避免在侧边栏逐级查找。', placement: 'top' },
    ],
  },
  {
    route: '/tasks',
    steps: [
      { selector: '.page-container', title: '任务管理', description: '任务是监控的基本单元，包含关键词、价格区间、执行模式与调度间隔。' },
      { selector: '.xh-btn-brand', title: '一键启动/新建任务', description: '顶部可「新增任务」或「全部启动」运行中的任务；状态筛选与自动实时搜索开关也在此。', placement: 'bottom' },
    ],
  },
  {
    route: '/tasks/new',
    steps: [
      { selector: '.page-container', title: '新建任务', description: '填写关键词与筛选条件，选择执行模式（通知/确认/自动/半自动），保存后任务即进入运行。' },
    ],
  },
  {
    route: '/tasks/:id',
    steps: [
      { selector: '.page-container', title: '任务详情', description: '查看任务运行状态、采集商品、抢单记录，并可嵌入「商品列表」Tab 管理与导出商品。' },
    ],
  },
  {
    route: '/items',
    steps: [
      { selector: '.page-container', title: '商品中心', description: '统一查看已采集商品，支持关键词/价格/已售/数据源筛选、实时搜索、导出与手动导入。' },
    ],
  },
  {
    route: '/orders',
    steps: [
      { selector: '.page-container', title: '抢单记录', description: '记录每次抢单尝试（成功/失败/超时/已接管），含金额、商品、失败原因与截图，可追踪状态流转。' },
    ],
  },
  {
    route: '/evaluations',
    steps: [
      { selector: '.page-container', title: '卖家评估', description: '从职业度、信用、纠纷、价格异动 4 维评估卖家，综合评分决定是否抢单；支持 AI 多模态深度分析。' },
    ],
  },
  {
    route: '/timeline',
    steps: [
      { selector: '.page-container', title: '事件时间线', description: '按时间倒序展示系统事件，可按键类型与级别过滤，统一贯穿所有模块用于回溯定位。' },
    ],
  },
  {
    route: '/logs',
    steps: [
      { selector: '.page-container', title: '实时日志', description: '通过 SSE 实时推送系统日志，按级别过滤并自动滚动，断线自动重连，适合运行时排查。' },
    ],
  },
  {
    route: '/logs/errors',
    steps: [
      { selector: '.page-container', title: '错误日志', description: '集中捕获未处理异常，按模块/级别/时间筛选，可导出含堆栈与任务状态的上下文用于 AI 诊断。' },
    ],
  },
  {
    route: '/notifications',
    steps: [
      { selector: '.page-container', title: '通知中心', description: '聚合订单/登录/系统/配置/任务五类通知，支持已读筛选与批量操作。' },
    ],
  },
  {
    route: '/price-dashboard',
    steps: [
      { selector: '.page-container', title: '价格行情', description: '分类对比、统计表、已成交区间与议价评估四种分析，辅助制定捡漏价格策略。' },
    ],
  },
  {
    route: '/config/price',
    steps: [
      { selector: '.page-container', title: '价格策略', description: '通过硬性上下限、市场参考价比例、同类低价 TopN 四组开关过滤商品，任务级配置优先。' },
    ],
  },
  {
    route: '/config/eval',
    steps: [
      { selector: '.page-container', title: '评估规则', description: '调整四维评估权重（总和须为 100）与评分阈值，权重变更对新任务生效。' },
    ],
  },
  {
    route: '/config/buyer',
    steps: [
      { selector: '.page-container', title: '抢单策略', description: '配置落单点击重试、提交超时、价格容差与人工接管窗口，运行时可调。' },
    ],
  },
  {
    route: '/config/search',
    steps: [
      { selector: '.page-container', title: '搜索参数', description: '配置分页大小、排序、区域过滤、翻页深度与闲鱼筛选标签。' },
    ],
  },
  {
    route: '/config/notifier',
    steps: [
      { selector: '.page-container', title: '通知渠道', description: '配置 Server酱/钉钉/企业微信/Telegram 等 7+ 渠道并发推送，含免打扰与优先级。' },
    ],
  },
  {
    route: '/config/ai',
    steps: [
      { selector: '.page-container', title: 'AI 服务', description: '配置 OpenAI 兼容 API 提供商、模型、预算上限与 Prompt；支持自然语言建任务与多模态鉴伪。' },
    ],
  },
  {
    route: '/config/chatbot',
    steps: [
      { selector: '.page-container', title: '客服配置', description: '配置智能客服的 RAG、Agent 工具调用、知识库、FAQ 与转人工策略。' },
    ],
  },
  {
    route: '/config/version',
    steps: [
      { selector: '.page-container', title: '配置版本', description: '每次配置修改自动保存版本，支持对比与一键回滚；支持导入导出。' },
    ],
  },
  {
    route: '/maintenance',
    steps: [
      { selector: '.page-container', title: '系统清理', description: '清理过期商品、历史事件、旧日志与缓存，支持 VACUUM 收缩 SQLite。' },
    ],
  },
  {
    route: '/maintenance/db',
    steps: [
      { selector: '.page-container', title: '数据库维护', description: '在线对 11 张业务表进行查看/编辑/删除，可执行 SQL 查询与 CSV 导入导出。' },
    ],
  },
  {
    route: '/maintenance/vector',
    steps: [
      { selector: '.page-container', title: '向量数据库维护', description: '管理 ChromaDB 快照、清理过期文档并监控重建进度，保障智能客服知识库可用。' },
    ],
  },
  {
    route: '/maintenance/tunnel',
    steps: [
      { selector: '.page-container', title: '内网穿透', description: '将本地 Web 控制台暴露到外网/局域网，支持 Cloudflare、cpolar、Tailscale。' },
    ],
  },
  {
    route: '/batch-refresh',
    steps: [
      { selector: '.page-container', title: '批量采集', description: '定时自动采集在售商品最新数据，检测已售与字段变更，支持熔断与断点续传。' },
    ],
  },
  {
    route: '/anticrawl',
    steps: [
      { selector: '.page-container', title: '反爬登录管理', description: '管理闲鱼登录态、Cookie 注入、多账号轮换与 QPS/延迟反爬策略，风控触发自动暂停。' },
    ],
  },
  {
    route: '/chatbot',
    steps: [
      { selector: '.page-container', title: '智能客服', description: 'RAG + Agent 双引擎助手，可查任务状态、读配置、搜错误日志并解答 FAQ，支持会话与转人工。' },
    ],
  },
  {
    route: '/export',
    steps: [
      { selector: '.page-container', title: '数据导出', description: '统一导出任务/商品/评估/订单四类 CSV，支持按任务与时间范围筛选并保存预设。' },
    ],
  },
  {
    route: '/menu-admin',
    steps: [
      { selector: '.page-container', title: '菜单管理', description: '拖拽排序、隐藏/显示侧边栏菜单项，配置按用户隔离保存，可一键重置。' },
    ],
  },
]

/** 全部引导路由列表：供"重新引导全部"入口与配置完整性测试使用 */
export const GUIDE_ROUTES: string[] = MENU_GUIDES.map((g) => g.route)

/** 按路由前缀匹配引导配置（支持 /tasks/:id 这类动态路由的先序匹配） */
export function findMenuGuide(pathname: string): MenuGuide | undefined {
  // 精确匹配优先
  const exact = MENU_GUIDES.find((g) => g.route === pathname)
  if (exact) return exact
  // 动态路由匹配：把 /tasks/:id 编译成正则，匹配 /tasks/123
  return MENU_GUIDES.find((g) => {
    if (!g.route.includes(':')) return false
    const re = new RegExp(`^${g.route.replaceAll(/:[^/]+/g, '[^/]+')}$`)
    return re.test(pathname)
  })
}
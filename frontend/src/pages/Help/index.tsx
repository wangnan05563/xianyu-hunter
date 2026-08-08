import { useState, useMemo } from 'react'
import { Layout, Typography, Anchor, Button, Space, Tag, Alert, Card, Divider, theme, Input } from 'antd'
import {
  ApiOutlined,
  RocketOutlined,
  DashboardOutlined,
  UnorderedListOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
  AuditOutlined,
  FieldTimeOutlined,
  FileTextOutlined,
  SettingOutlined,
  ToolOutlined,
  SearchOutlined,
  BulbOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  DollarOutlined,
  BellOutlined,
  RobotOutlined,
  MessageOutlined,
  DatabaseOutlined,
  CloudDownloadOutlined,
  ExperimentOutlined,
  AppstoreOutlined,
  BugOutlined,
  InfoCircleOutlined,
  TeamOutlined,
  GlobalOutlined,
} from '@ant-design/icons'
import type React from 'react'
import { useTheme } from '../../contexts/ThemeContext'
import { API_BASE } from '../../utils/apiBase'

const { Sider, Content } = Layout
const { Title, Paragraph, Text } = Typography

// ============ 文档内容数据结构 ============
// 将内容抽象为数据，便于维护和扩展；渲染逻辑与内容分离
interface DocBlock {
  type: 'feature' | 'steps' | 'scenario' | 'config' | 'note'
  title: string
  content: React.ReactNode
}

interface DocSection {
  id: string
  title: string
  icon: React.ReactNode
  intro: string
  blocks: DocBlock[]
}

// 通用块构造器：减少重复 JSX 模板
const feature = (title: string, content: React.ReactNode): DocBlock => ({ type: 'feature', title, content })
const steps = (title: string, items: string[]): DocBlock => ({
  type: 'steps',
  title,
  content: (
    <ol style={{ paddingLeft: 20, margin: 0 }}>
      {/* S6479：用步骤文本作 key 而非数组下标，避免重排导致状态错乱 */}
      {items.map((s) => (
        <li key={s} style={{ marginBottom: 6 }}>{s}</li>
      ))}
    </ol>
  ),
})
const scenario = (title: string, content: React.ReactNode): DocBlock => ({ type: 'scenario', title, content })
const config = (title: string, rows: [string, string, string][]): DocBlock => ({
  type: 'config',
  title,
  content: (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: 'var(--xh-bg-spotlight)' }}>
            <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--xh-border)', width: '30%' }}>参数</th>
            <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--xh-border)', width: '20%' }}>示例</th>
            <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--xh-border)' }}>说明</th>
          </tr>
        </thead>
        <tbody>
          {/* S6479：用参数名作 key 而非下标 */}
          {rows.map(([k, v, d]) => (
            <tr key={k}>
              <td style={{ padding: '8px 12px', borderBottom: '1px solid var(--xh-border)' }}><Text code>{k}</Text></td>
              <td style={{ padding: '8px 12px', borderBottom: '1px solid var(--xh-border)', color: 'var(--xh-text-secondary)' }}>{v}</td>
              <td style={{ padding: '8px 12px', borderBottom: '1px solid var(--xh-border)', color: 'var(--xh-text-secondary)' }}>{d}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ),
})
const note = (title: string, content: React.ReactNode, type: 'info' | 'warning' = 'info'): DocBlock => ({
  type: 'note',
  title,
  content: <Alert type={type} showIcon message={content} style={{ marginTop: 0 }} />,
})

// ============ 完整文档内容 ============
// 章节排序与 menu_registry.yaml category 一致：overview → data_view → config → maintenance → other
const DOC_SECTIONS: DocSection[] = [
  {
    id: 'quickstart',
    title: '快速开始',
    icon: <RocketOutlined />,
    intro: '从安装到首次跑通任务的完整流程，新用户必读。',
    blocks: [
      feature('核心功能', '闲鱼猎人是闲鱼自动捡漏与抢单工具，支持关键词搜索、价格过滤、卖家评估、自动下单和多渠道通知，并提供 Web 控制台、移动端、AI 智能客服等完整能力。'),
      steps('操作步骤', [
        '安装依赖：pip install -r requirements.txt && playwright install chromium',
        '复制配置：copy .env.example .env，填入推送 Key（Server酱 / PushPlus / Bark / 钉钉 / 企业微信 / Telegram）',
        '首次登录：python -m xianyu_hunter login，弹出浏览器扫码登录闲鱼',
        // S7780：用 String.raw 避免转义反斜杠，Windows 路径更清晰
        String.raw`启动服务：双击 scripts\启动服务.bat，或 python -m xianyu_hunter web --with-scheduler`,
        '访问控制台：浏览器打开 http://127.0.0.1:8001/xianyu/（移动端自动跳转 /m）',
        '创建任务：在「任务管理」页面新建监控任务，设置关键词和价格区间',
        '启动任务：任务创建后默认为 RUNNING 状态，调度器会按间隔自动执行',
      ]),
      scenario('使用场景', '刚部署完系统，需要从零开始配置并跑通第一个监控任务。'),
      note('注意事项', <>首次登录需人工扫码，登录态持久化到仓库根目录的 <Text code>./browser-data</Text>。若触发风控滑块会自动暂停，需重新登录。控制台默认开启 Token 鉴权；若 <Text code>.env</Text> 中未设置 <Text code>WEB_TOKEN</Text>，系统会自动生成并写入 .env，无需手动必填。</>, 'warning'),
    ],
  },
  {
    id: 'about',
    title: '关于 / 版本信息',
    icon: <InfoCircleOutlined />,
    intro: '系统元信息与文档资源统一入口。',
    blocks: [
      feature('核心功能', '展示当前版本号、发布日期、Git SHA；一键检查 GitHub 最新版本；汇总 8 项资源入口（用户协议、隐私条款、开源声明、帮助文档、API 文档、联系我们、官方社区、报告问题，其中帮助文档与开源声明为内部页面，其余为外部链接）；浏览 41 项前后端依赖的开源许可清单（前端 21 + 后端 20）。'),
      steps('操作步骤', [
        '点击侧边栏「其他」→「关于」，或在顶栏点击 ℹ️ 图标',
        '查看版本号、发布日期、Git SHA 等元信息',
        '点击「检查更新」按钮查询 GitHub 最新发布',
        '点击菜单列表项跳转外部资源或打开开源声明 Modal',
        '在 Modal 搜索框按包名/许可证过滤依赖',
      ]),
      note('注意事项', '自动检查更新：进入页面 5 秒后首次检查，之后每 60 分钟检查一次；后端 5 分钟缓存避免触发 GitHub 限流。', 'warning'),
    ],
  },
  {
    id: 'dashboard',
    title: '仪表盘',
    icon: <DashboardOutlined />,
    intro: '系统总览入口，集中展示 KPI、告警、事件流和价格分布。',
    blocks: [
      feature('核心功能', '展示今日抢单数、评估数、任务数等关键指标；告警雷达扫描失败订单、超时订单、低分评估；事件流时间线呈现系统实时活动；价格分布直方图与趋势分析。'),
      steps('操作步骤', [
        '进入控制台首页即为仪表盘',
        '查看顶部 KPI 卡片了解整体运行情况',
        '点击告警雷达查看失败订单、超时订单、低分评估详情',
        '观察事件流了解系统实时活动',
        '点击价格分布直方图查看趋势详情',
      ]),
      scenario('使用场景', '日常运维时快速了解系统运行状态，发现异常及时处理。'),
      note('注意事项', 'KPI 指标每 5 分钟刷新，概览卡片与迷你图每 60 秒刷新；调度器状态指示灯绿色表示运行中，红色表示已停止。'),
    ],
  },
  {
    id: 'tasks',
    title: '任务管理',
    icon: <UnorderedListOutlined />,
    intro: '创建、编辑、启停监控任务，管理任务依赖关系。',
    blocks: [
      feature('核心功能', '任务是监控的基本单元，包含关键词、价格区间、执行模式、调度间隔等。支持 start/pause/resume/stop 控制；任务间依赖（DAG）；任务级 AI 评估配置、任务级价格/搜索/反检测覆盖。'),
      steps('操作步骤', [
        '点击「新建任务」进入任务编辑器',
        '填写关键词（如 iPhone 15 Pro）',
        '设置价格区间（最低价 / 最高价）',
        '选择执行模式（notify / confirm / auto / semi_auto）',
        '设置调度间隔（interval_seconds，建议 ≥ 60 秒）',
        '可选：配置 Cron 表达式实现定时调度',
        '可选：配置闲鱼筛选标签（个人闲置 / 已验真 / 担保交易 / 包邮等）',
        '可选：配置任务级 AI 评估阈值与自定义 Prompt',
        '保存后任务默认为 RUNNING 状态',
      ]),
      config('参数配置', [
        ['keyword', 'iPhone 15', '搜索关键词，必填'],
        ['min_price', '1500', '价格下限（元），留空不限'],
        ['max_price', '2500', '价格上限（元），留空不限'],
        ['max_publish_days', '7', '仅采集最近 N 天内发布的商品'],
        ['mode', 'auto', '执行模式：notify/confirm/auto/semi_auto'],
        ['interval_seconds', '120', '调度间隔（秒），建议 60-300'],
        ['cron', '0 */2 * * *', 'Cron 表达式，设置后覆盖 interval'],
        ['search_filters', '["personal_idle","verified"]', '闲鱼筛选标签 JSON 数组'],
        ['exclude_words', '["抽奖","拼单"]', '排除词列表'],
        ['eval_threshold', '70', '任务级评估阈值（None 沿用全局）'],
      ]),
      scenario('使用场景', <>监控特定商品捡漏：如设置 <Text code>keyword=iPhone 15</Text>、价格 1500-2500、模式 auto，系统会自动搜索、评估并抢单。</>),
      note('注意事项', <>执行模式说明：<Tag color="blue">notify</Tag>仅通知 <Tag color="orange">confirm</Tag>确认后执行 <Tag color="green">auto</Tag>自动抢单 <Tag color="purple">semi_auto</Tag>半自动。高频任务（&lt;60秒）有封号风险。</>, 'warning'),
    ],
  },
  {
    id: 'items',
    title: '商品中心',
    icon: <ShoppingOutlined />,
    intro: '商品数据统一入口，围绕任务聚合展示、搜索、抢单、导入导出。',
    blocks: [
      feature('核心功能', '嵌入在「任务详情」内的商品列表 Tab，支持卡片/列表视图切换、多维度筛选（关键词/价格/已售/数据源）、实时搜索、官方采集、直播采集、一键抢单（30 秒冷却保护）、已售检测与标记、CSV 导出、手动导入。系统自动增量去重，已抓取商品不重复评估。'),
      steps('操作步骤', [
        '进入「任务管理」→ 点击目标任务进入任务详情',
        '切换到「商品列表」Tab',
        '使用筛选器按关键词、价格、已售状态、数据源过滤',
        '切换卡片/列表视图',
        '点击商品查看详情（标题、价格、卖家、发布时间、缩略图、想要数）',
        '评估通过的商品可点击「抢单」（30 秒冷却）',
        '已售商品自动标记，记录检测时间',
        '点击「导出 CSV」按当前筛选导出',
      ]),
      scenario('使用场景', '回顾历史抓取记录，分析某类商品的价格分布和卖家特征；或在任务上下文中快速操作抢单与导出。'),
      note('注意事项', '商品中心为顶部独立菜单页面，也可在「任务详情」内的商品列表 Tab 进入；数据源通过标签颜色区分（搜索/官方/直播）。', 'warning'),
    ],
  },
  {
    id: 'evaluations',
    title: '卖家评估',
    icon: <AuditOutlined />,
    intro: '4 维卖家评估模型及评分解读。',
    blocks: [
      feature('核心功能', '从职业度、信用、纠纷、价格异动 4 个维度评估卖家，综合评分决定是否抢单。支持 AI 多模态深度分析、商品图鉴伪、卖家模板检测。评估规则可在「评估规则」配置页调整。'),
      steps('操作步骤', [
        '进入「卖家评估」页面',
        '查看评估列表，按分数排序',
        '点击评估查看 4 维细分评分',
        '使用热力图分析评分分布',
        '点击「AI 深度分析」获取多模态评估结果',
        '查看趋势 sparkline 了解卖家变化',
      ]),
      config('评分维度', [
        ['职业度', '0-100', '卖家专业程度，越高越可靠'],
        ['信用', '0-100', '信用评级，反映历史交易信誉'],
        ['纠纷', '0-100', '纠纷率，越低越好'],
        ['价格异动', '0-100', '价格波动异常度，越低越稳定'],
      ]),
      scenario('使用场景', '分析卖家质量，调整评估阈值以过滤低质量卖家；对可疑卖家触发 AI 鉴伪。'),
      note('注意事项', '评估阈值在「评估规则」配置页调整；评分低于阈值会自动跳过抢单。'),
    ],
  },
  {
    id: 'orders',
    title: '抢单记录',
    icon: <ThunderboltOutlined />,
    intro: '查看所有抢单记录及状态流转。',
    blocks: [
      feature('核心功能', '记录每次抢单尝试，包含订单状态（成功/失败/超时/已接管）、金额、商品信息、失败原因、截图等。支持利润计算、状态流转追踪、人工接管标记。'),
      steps('操作步骤', [
        '进入「抢单记录」页面',
        '按状态筛选（成功/失败/超时/已接管）',
        '点击订单查看详情',
        '失败订单可查看失败原因和截图',
        '对超时订单可手动标记为「已接管」',
      ]),
      scenario('使用场景', '排查抢单失败原因，统计成功率，分析失败模式。'),
      note('注意事项', <>抢单窗口通常 &lt; 30 秒，对网络延迟敏感。价格容差校验失败会记录为 <Tag color="red">price_mismatch</Tag>。</>, 'warning'),
    ],
  },
  {
    id: 'timeline',
    title: '事件时间线',
    icon: <FieldTimeOutlined />,
    intro: '系统事件流的可视化展示，支持筛选。',
    blocks: [
      feature('核心功能', '按时间倒序展示系统事件（覆盖后端 EventType 枚举定义的 36 种事件类型，含任务生命周期、商品/评估、购买、通知、风控、认证、系统维护、智能客服等），支持按事件类型和级别（INFO/WARN/ERROR）筛选，统一时间线贯穿所有模块。'),
      steps('操作步骤', [
        '进入「事件时间线」页面',
        '使用筛选器按事件类型过滤',
        '点击事件查看详情',
        '支持按级别（INFO/WARN/ERROR）筛选',
      ]),
      scenario('使用场景', '回溯问题发生时间线，定位异常事件的上下文。'),
      note('注意事项', '事件存储在 SQLite，长期运行后可定期清理历史事件。'),
    ],
  },
  {
    id: 'logs',
    title: '实时日志',
    icon: <FileTextOutlined />,
    intro: '实时查看系统日志，支持 SSE 流式推送。',
    blocks: [
      feature('核心功能', '通过 SSE（Server-Sent Events）实时推送日志，支持按级别（DEBUG/INFO/WARN/ERROR）过滤，自动滚动。同时写入 data/logs/*.log（按日滚动），SSE 断连自动重连。'),
      steps('操作步骤', [
        '进入「实时日志」页面',
        '选择日志级别过滤',
        '实时观察日志输出',
        '可暂停自动滚动以便查看',
      ]),
      scenario('使用场景', '实时监控任务执行过程，排查运行时问题。'),
      note('注意事项', '日志同时写入 data/logs/*.log（按日滚动）；SSE 连接断开会自动重连。'),
    ],
  },
  {
    id: 'error-logs',
    title: '错误日志',
    icon: <BugOutlined />,
    intro: '后台异常捕获与 AI 诊断上下文。',
    blocks: [
      feature('核心功能', '专门捕获未处理异常与系统错误事件，支持按模块/级别/时间筛选；可导出错误上下文（含堆栈、相关日志、任务状态）用于 AI 诊断或人工排查。'),
      steps('操作步骤', [
        '进入「错误日志」页面',
        '按模块/级别/时间范围筛选',
        '点击错误查看完整堆栈',
        '点击「导出上下文」获取诊断信息',
        '复制堆栈到「智能客服」获取 AI 修复建议',
      ]),
      scenario('使用场景', '系统异常时快速定位错误，导出上下文供 AI 客服分析。'),
      note('注意事项', '错误日志通过全局异常处理器自动采集，无需手工埋点。', 'warning'),
    ],
  },
  {
    id: 'notifications',
    title: '通知中心',
    icon: <BellOutlined />,
    intro: '系统通知列表与已读管理。',
    blocks: [
      feature('核心功能', '聚合所有系统通知（订单 / 登录 / 系统 / 配置 / 任务五大类），支持按已读/未读筛选、批量标记已读、删除；URL 参数保留筛选状态（刷新不丢失）。'),
      steps('操作步骤', [
        '点击顶栏铃铛图标或侧边栏「通知中心」',
        '使用顶部分段控件切换 全部/未读/已读',
        '点击通知查看详情',
        '使用「全部已读」批量标记',
        '可选中通知后批量删除',
      ]),
      scenario('使用场景', '集中查看系统通知（订单成功、风控告警、配置变更等），避免遗漏重要事件。'),
      note('注意事项', '通知通过 NotificationEngine 统一调度，与推送渠道（钉钉/企微等）解耦。', 'warning'),
    ],
  },
  {
    id: 'price-dashboard',
    title: '价格行情',
    icon: <DollarOutlined />,
    intro: '价格数据分析与多维度对比看板。',
    blocks: [
      feature('核心功能', '提供 4 类价格分析：分类对比（按商品类目横向对比中位价/最低价/最高价）、分类统计表、已成交价格区间、议价评估（BargainEval）。支持 TopN、市场参考价、议价幅度分析。'),
      steps('操作步骤', [
        '进入「价格行情」页面',
        '切换不同 Tab 查看分类对比 / 统计 / 已成交 / 议价',
        '使用筛选器选择时间范围与类目',
        '点击图表元素下钻到具体商品',
      ]),
      scenario('使用场景', '分析某类商品的历史成交价区间，制定合理的捡漏价格策略。'),
      note('注意事项', '议价评估基于历史成交数据，新类目数据不足时仅供参考。', 'warning'),
    ],
  },
  {
    id: 'config-price',
    title: '价格策略',
    icon: <SettingOutlined />,
    intro: '配置价格过滤规则与低价捡漏策略。',
    blocks: [
      feature('核心功能', '通过 4 组独立开关过滤商品：硬性价格上限（max_price）、硬性价格下限（min_price，防 1 元引流）、低于市场参考价比例（market_ratio）、同类低价 TopN（top_n）。每组均可单独启用/停用，任务级价格区间优先于全局配置。'),
      config('参数配置', [
        ['enabled_max / max_price', 'true / 10000', '开启后价格高于上限的商品被过滤'],
        ['enabled_min / min_price', 'true / 100', '开启后价格低于下限的商品被过滤（防引流）'],
        ['enabled_market_ratio / market_ratio', 'false / 0.8', '开启后低于市场参考价该比例的商品被过滤'],
        ['enabled_top_n / top_n', 'false / 5', '开启后仅保留同类低价前 N 件'],
      ]),
      note('注意事项', '以上为各组的默认开关与默认值，实际以当前配置为准；任务级价格区间优先于全局配置。', 'warning'),
    ],
  },
  {
    id: 'config-eval',
    title: '评估规则',
    icon: <SettingOutlined />,
    intro: '调整 4 维评估权重与评分阈值。',
    blocks: [
      feature('核心功能', '配置 4 个评估维度的权重（职业度 / 信用 / 纠纷 / 价格异动），权重总和必须为 100（否则校验报错）。支持 Sigmoid 扣分曲线、信用分一票否决、阈值建议。'),
      config('参数配置', [
        ['professional', '30', '职业度权重（%），总和需为 100'],
        ['credit', '30', '信用权重（%）'],
        ['dispute', '25', '纠纷权重（%）'],
        ['price', '15', '价格异动权重（%）'],
        ['pass_score', '60', '综合评分下限，低于则跳过抢单（配置文件可覆盖，如 75）'],
        ['credit_score_min', '60', '信用分一票否决下限，低于直接拒'],
      ]),
      note('注意事项', '权重总和必须为 100%，否则保存报错；修改后对新任务生效。', 'warning'),
    ],
  },
  {
    id: 'config-buyer',
    title: '抢单策略',
    icon: <SettingOutlined />,
    intro: '配置落单点击、超时与价格容差。',
    blocks: [
      feature('核心功能', '配置落单流程的点击重试、提交订单超时、拍下价格容差、落单间隔与人工接管窗口（替代 buyer_config.py 硬编码，运行时可调）。'),
      config('参数配置', [
        ['click_retry_times', '2', '点击「立即购买」按钮的重试次数'],
        ['click_retry_interval', '1.0', '两次点击之间的退避间隔（秒）'],
        ['confirm_button_timeout', '10.0', '等待「提交订单」按钮出现的超时（秒）'],
        ['price_tolerance', '0.05', '拍下价格相对预期价格的允许偏差（5%）'],
        ['min_interval_between_orders', '0.0', '两次落单之间的最小间隔（秒）'],
        ['takeover_timeout_min', '30', '人工接管窗口（分钟）'],
      ]),
      note('注意事项', '价格容差防止抢单时价格突变导致错价；接管窗口用于人工介入，超时将自动放弃。', 'warning'),
    ],
  },
  {
    id: 'config-search',
    title: '搜索参数',
    icon: <SearchOutlined />,
    intro: '配置搜索分页、排序、区域与筛选标签。',
    blocks: [
      feature('核心功能', '设置搜索结果分页大小、排序方式、区域过滤、翻页深度与闲鱼筛选标签。反检测相关的全局 QPS / 延迟 / 熔断在「反爬登录管理」中配置。'),
      config('参数配置', [
        ['page_size', '50', '单次搜索返回的商品条目数'],
        ['sort_type', 'default', '排序：default/newest/price_asc/price_desc/want_count'],
        ['timeout', '30', '单次搜索请求的最大等待（秒）'],
        ['regions', '（空）', '区域过滤，逗号分隔，空表示全国'],
        ['max_pages', '5', '搜索结果翻页深度（每屏约 20-26 条）'],
        ['filter_tags', '[]', '闲鱼筛选标签列表（如 personal_idle / 包邮）'],
      ]),
      note('注意事项', 'page_size 与 max_pages 过大将增加风控风险与耗时，建议按需调整。', 'warning'),
    ],
  },
  {
    id: 'config-notifier',
    title: '通知渠道',
    icon: <SettingOutlined />,
    intro: '配置多渠道通知及免打扰时段。',
    blocks: [
      feature('核心功能', '支持 Server酱、PushPlus、Bark、钉钉、企业微信、Telegram、ntfy、通用 Webhook 等 7+ 渠道并发推送，可配置免打扰时段、事件订阅、模板。'),
      steps('操作步骤', [
        '进入「通知渠道」配置页',
        '点击渠道卡片启用/禁用',
        '填入对应渠道的 Token/Key',
        '可拖拽排序渠道优先级',
        '配置免打扰时段（如 23:00-07:00）',
        '点击测试发送验证配置',
      ]),
      scenario('使用场景', '匹配到目标商品时立即收到通知，多渠道并发确保不漏报。'),
      note('注意事项', '推送 Key 加密存储在系统 keyring（Windows DPAPI），不写入配置文件。', 'warning'),
    ],
  },
  {
    id: 'config-ai',
    title: 'AI 服务',
    icon: <SettingOutlined />,
    intro: '配置 AI 模型、预算和 Prompt。',
    blocks: [
      feature('核心功能', '支持 OpenAI 兼容 API（含 9 家提供商预设：OpenAI / DeepSeek / 智谱 GLM / Moonshot / 通义千问 / 文心一言 / 豆包 / Agnes AI / Ollama 本地），用于自然语言建任务、商品深度分析、多模态鉴伪。Embedding 后端可选本地 sentence-transformers（BAAI/bge-small-zh-v1.5, dim=512）、OpenAI、Jina、Ollama 或复用 LLM 配置。可配置模型、预算上限、用量统计、Prompt 编辑器。'),
      config('参数配置', [
        ['api_base', 'https://api.openai.com/v1', 'API 基础地址'],
        ['api_key', 'sk-...', 'API Key（加密存储）'],
        ['model', 'gpt-4o-mini', '模型名称'],
        ['budget_daily', '1.0', '每日预算上限（美元）'],
        ['budget_monthly', '20.0', '每月预算上限（美元）'],
        ['embedding_backend', 'local', 'embedding 后端：local / openai / jina / ollama / inherit（复用 LLM）'],
      ]),
      scenario('使用场景', '用自然语言描述需求（如"监控 iPhone 15 2500 以内"），AI 自动创建任务；或对可疑商品触发 AI 多模态鉴伪。'),
      note('注意事项', '超出预算上限会自动停止 AI 调用；Prompt 可在「Prompt 编辑器」自定义。Embedding 本地后端无需外部 API，避免网络问题。', 'warning'),
    ],
  },
  {
    id: 'config-chatbot',
    title: '客服配置',
    icon: <MessageOutlined />,
    intro: '智能客服模块配置：RAG / Agent / 知识库 / FAQ / 转人工。',
    blocks: [
      feature('核心功能', '配置智能客服的 5 大子模块：RAG 检索增强生成、Agent 工具调用、知识库（KB）管理、FAQ 问答库、人工接管（escalation）策略。支持知识库定时自动更新、审计日志、欢迎语自定义。'),
      config('参数配置', [
        ['top_k', '5', 'RAG 检索返回的片段数量（1-20）'],
        ['similarity_threshold', '0.65', 'RAG 相似度阈值，低于此值的片段丢弃'],
        ['enable_tools', 'true', '是否启用 Agent 工具调用'],
        ['auto_update_enabled', 'true', '知识库是否定时自动更新'],
        ['update_interval_hours', '6', '知识库自动更新间隔（小时）'],
      ]),
      steps('操作步骤', [
        '进入「客服配置」页面',
        '配置 RAG 检索参数与 Agent 启用',
        '在「FAQ」Tab 管理问答库',
        '查看「审计日志」追踪配置变更',
        '配置欢迎语与转人工触发规则',
      ]),
      scenario('使用场景', '调整 AI 客服回答的准确性边界，让系统自动调用工具完成任务（如查任务状态、读错误日志）。'),
      note('注意事项', '知识库修改后会触发后台重建，期间检索结果可能短暂来自旧版本；转人工默认在用户连续点踩 2 次时触发。', 'warning'),
    ],
  },
  {
    id: 'config-version',
    title: '配置版本',
    icon: <SettingOutlined />,
    intro: '配置版本管理与回滚。',
    blocks: [
      feature('核心功能', '每次配置修改自动保存版本，支持版本对比和一键回滚；支持配置导入/导出（含脱敏）。'),
      steps('操作步骤', [
        '进入「配置版本」页面',
        '查看历史版本列表',
        '选择两个版本对比差异',
        '点击「回滚」恢复到历史版本',
      ]),
      scenario('使用场景', '配置修改后系统异常，快速回滚到上一个正常版本。'),
      note('注意事项', '配置自动备份到 config/backups/；回滚操作本身也会生成新版本。', 'warning'),
    ],
  },
  {
    id: 'maintenance-cleanup',
    title: '系统清理',
    icon: <ToolOutlined />,
    intro: '清理历史数据、缓存、日志。',
    blocks: [
      feature('核心功能', '清理过期商品、历史事件、旧日志、浏览器缓存等，释放磁盘空间；支持 VACUUM 收缩 SQLite。'),
      steps('操作步骤', [
        '进入「系统清理」页面',
        '选择清理项目（商品/事件/日志/缓存）',
        '设置保留天数',
        '点击「执行清理」',
      ]),
      scenario('使用场景', '长期运行后磁盘占用过高，定期清理历史数据。'),
      note('注意事项', '清理操作不可逆，建议先备份；清理时服务可能短暂响应变慢。', 'warning'),
    ],
  },
  {
    id: 'maintenance-db',
    title: '数据库维护',
    icon: <DatabaseOutlined />,
    intro: '在线管理数据库表数据。',
    blocks: [
      feature('核心功能', '提供 11 张业务表的在线 CRUD 操作（tasks / items / sellers / evaluations / orders / events / task_links / task_deps / notifications / accounts / proxies），支持查看、编辑、删除记录，执行 SQL 查询，导入导出 CSV。'),
      steps('操作步骤', [
        '进入「数据库维护」页面',
        '选择业务表',
        '查看表结构和数据',
        '可执行自定义 SQL 查询',
        '支持导出查询结果为 CSV',
      ]),
      scenario('使用场景', '直接查看或修改数据库记录，排查数据问题。'),
      note('注意事项', '直接操作数据库有风险，建议先备份；生产环境慎用 DELETE 操作。', 'warning'),
    ],
  },
  {
    id: 'maintenance-vector',
    title: '向量数据库维护',
    icon: <DatabaseOutlined />,
    intro: 'ChromaDB 知识库快照、清理与监控。',
    blocks: [
      feature('核心功能', '管理 ChromaDB 向量数据库：查看 collection 列表、文档数量、占用空间；创建快照备份、清理过期文档、监控重建进度；查看审计日志。'),
      steps('操作步骤', [
        '进入「向量数据库维护」页面',
        '查看 collection 列表与统计',
        '点击「创建快照」备份当前状态',
        '按时间/标签清理过期文档',
        '触发知识库重建并查看进度',
      ]),
      scenario('使用场景', '智能客服回答不准时，检查知识库是否过期；定期快照防止数据丢失。'),
      note('注意事项', '快照文件较大，建议清理前先确认磁盘空间；知识库重建期间检索会回退到 BM25。', 'warning'),
    ],
  },
  {
    id: 'maintenance-batch',
    title: '批量采集',
    icon: <CloudDownloadOutlined />,
    intro: '定时批量采集在售商品最新数据。',
    blocks: [
      feature('核心功能', '按设定间隔（默认 60 分钟，可调 1-1440）自动采集所有在售商品的最新详情，检测两类变化：已售状态、字段变更。支持手动触发、暂停/继续/停止、失败熔断（连续失败 3 次）、断点续传、执行历史。'),
      steps('操作步骤', [
        '进入「批量采集」页面',
        '调整采集间隔（1-1440 分钟）',
        '点击「立即触发」手动启动',
        '执行中可暂停/继续/停止',
        '查看「执行历史」标签页',
      ]),
      scenario('使用场景', '长期运营时保持商品库新鲜度，及时下线已售商品。'),
      note('注意事项', '连续失败 3 次自动熔断停止当前批次；中断后下次从断点继续。', 'warning'),
    ],
  },
  {
    id: 'anticrawl',
    title: '反爬登录管理',
    icon: <ExperimentOutlined />,
    intro: '管理闲鱼登录态、Cookie 轮换、反爬策略。',
    blocks: [
      feature('核心功能', '管理闲鱼账号登录状态，支持扫码登录、Cookie 注入（浏览器/手动/CDP）、多账号轮换、反爬策略配置、会话健康检查、指纹伪装、QPS 控制、Cookie 分层管理。'),
      steps('操作步骤', [
        '进入「反爬登录管理」页面',
        '查看当前登录状态和 Cookie 有效性',
        '点击「扫码登录」重新登录',
        '或点击「Cookie 注入」手动导入 Cookie',
        '配置反爬策略（QPS、延迟、失败暂停阈值）',
        '多账号可在此添加和轮换',
      ]),
      config('反爬参数', [
        ['qps', '5', '全局每秒请求数上限'],
        ['min_delay_ms', '3000', '操作最小间隔（毫秒）'],
        ['max_delay_ms', '4500', '操作最大间隔（毫秒）'],
        ['fail_pause_threshold', '3', '连续失败 N 次触发熔断暂停'],
        ['fail_window_sec', '3600', '失败计数统计窗口（秒）'],
      ]),
      scenario('使用场景', '登录态失效后重新登录；风控触发后调整反爬策略降低频率；多账号轮换分摊风险。'),
      note('注意事项', <>触发闲鱼 WAF 会自动暂停任务；连续失败请检查 <Text code>infra/selectors.py</Text> 是否需要更新。</>, 'warning'),
    ],
  },
  {
    id: 'tunnel',
    title: '内网穿透',
    icon: <GlobalOutlined />,
    intro: '将本地 Web 服务暴露到公网/局域网，支持远程访问。',
    blocks: [
      feature('核心功能', '为本地运行的 Web 控制台（默认端口 8001）建立内网穿透隧道，便于远程或移动端访问。支持 3 种 provider：Cloudflare（quick 临时域名 / named 固定域名）、cpolar、Tailscale。可配置 local_port、auto_start 与 tunnel_mode。'),
      config('参数配置', [
        ['provider', 'cloudflare', '穿透服务提供方：cloudflare / cpolar / tailscale'],
        ['local_port', '0', '隧道转发到的本地端口，0 表示从 server.port 继承'],
        ['auto_start', 'false', '后端启动时是否自动启动隧道'],
        ['tunnel_mode', 'quick', 'Cloudflare 模式：quick 临时域名 / named 固定域名'],
        ['hostname', '（空）', 'named 模式下的固定域名（需已在 Cloudflare DNS 托管）'],
      ]),
      steps('操作步骤', [
        '进入「内网穿透」页面（系统维护分组）',
        '选择 provider 并填入相应凭证（如 cpolar 的 authtoken）',
        'Cloudflare 可选 quick / named 模式',
        '保存后点击启动，复制生成的访问地址',
        '移动端或远程浏览器打开该地址即可访问控制台',
      ]),
      scenario('使用场景', '服务器部署在家庭/内网环境时，通过穿透隧道从外部网络或手机访问 Web 控制台。'),
      note('注意事项', 'Cloudflare named 模式需已托管域名与 Cloudflare 账号；自动下载的 CLI 二进制较大，首次启动可能较慢。', 'warning'),
    ],
  },
  {
    id: 'accounts',
    title: '多账号管理',
    icon: <TeamOutlined />,
    intro: '顶栏账号切换器：多闲鱼账号列表、切换、退出与会话事件。',
    blocks: [
      feature('核心功能', '通过顶栏账号切换器管理多个闲鱼账号：列表展示（含头像、昵称、最后活跃、状态）、一键切换（自动失效旧 Cookie 缓存并重置全局轮换层状态）、退出当前账号（撤销 session）、查询会话事件日志（登录/切换/退出）。'),
      steps('操作步骤', [
        '在「反爬登录管理」页面添加并登录多个闲鱼账号',
        '点击顶栏账号切换器查看已登录账号列表',
        '点击目标账号切换（自动失效旧 Cookie 缓存）',
        '点击「退出」撤销当前账号 session',
        '查看「会话事件」追踪所有账号的登录/切换/退出变更',
      ]),
      scenario('使用场景', '多账号轮换分摊风控风险；不同账号监控不同类目商品。'),
      note('注意事项', 'default 用户不可删除但可退出；切换账号会失效旧 Cookie 缓存并重置全局轮换层状态。', 'warning'),
    ],
  },
  {
    id: 'chatbot',
    title: '智能客服',
    icon: <RobotOutlined />,
    intro: 'RAG + Agent 双引擎的智能助手。',
    blocks: [
      feature('核心功能', '基于 RAG 检索 + Agent 工具调用的智能客服：可查询任务状态、读取配置值、搜索错误日志、解答 FAQ。支持会话管理（多会话/收藏/历史）、消息反馈（点赞/点踩）、转人工、上下文记忆。知识库覆盖 6 大训练语料（API 手册、配置参考、对话记录、领域知识、FAQ、故障排查）。'),
      steps('操作步骤', [
        '点击顶栏机器人图标或侧边栏「智能客服」',
        '在欢迎页选择快捷指令或自由提问',
        '查看 AI 回复（含引用来源）',
        '对回答进行反馈（👍/👎）',
        '复杂问题可点击「转人工」',
        '在左侧会话列表管理历史会话',
      ]),
      scenario('使用场景', '新用户咨询功能用法；排查报错时贴堆栈让 AI 分析；查询任务/订单状态。'),
      note('注意事项', 'AI 回答仅供参考，重要操作前请人工确认；消息支持「撤回」修改后重新生成。', 'warning'),
    ],
  },
  {
    id: 'export',
    title: '数据导出',
    icon: <CloudDownloadOutlined />,
    intro: '任务/商品/评估/订单四类数据集 CSV 导出。',
    blocks: [
      feature('核心功能', '统一导出入口：按任务/时间范围筛选后导出 CSV，支持商品、评估、订单、事件四类数据集。可保存常用导出为预设，重复使用。'),
      steps('操作步骤', [
        '进入「数据导出」页面',
        '选择数据集类型（商品/评估/订单/事件）',
        '选择任务范围与时间范围',
        '点击「导出」生成 CSV',
      ]),
      scenario('使用场景', '运营周报、月度数据分析；离线备份关键数据。'),
      note('注意事项', '大量数据导出可能耗时，建议分批或按时间分片。', 'warning'),
    ],
  },
  {
    id: 'menu-admin',
    title: '菜单管理',
    icon: <AppstoreOutlined />,
    intro: '用户级菜单可见性/排序配置。',
    blocks: [
      feature('核心功能', '允许用户自定义侧边栏菜单：拖拽排序、隐藏/显示不需要的菜单项，配置按用户隔离保存。配置存储在 SQLite（user_menu_configs 表），重置后恢复默认。'),
      steps('操作步骤', [
        '进入「菜单管理」页面',
        '拖拽菜单项调整顺序',
        '点击眼睛图标切换显示/隐藏',
        '点击「保存」写入偏好',
        '可点击「重置」恢复默认',
      ]),
      scenario('使用场景', '专注特定工作流时隐藏无关菜单；不同角色（运营/管理员）展示不同菜单组合。'),
      note('注意事项', '菜单配置与登录用户绑定，不影响其他用户；菜单项仅控制侧边栏显示，不影响 API 访问权限。', 'warning'),
    ],
  },
]

// ============ 块渲染器 ============
function renderBlock(block: DocBlock): React.ReactNode {
  const blockStyle = { marginBottom: 20 }
  const titleStyle: React.CSSProperties = {
    fontSize: 15,
    fontWeight: 600,
    marginBottom: 8,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  }
  switch (block.type) {
    case 'feature':
      return (
        <div style={blockStyle}>
          <div style={titleStyle}><BulbOutlined style={{ color: '#1677ff' }} />{block.title}</div>
          <Paragraph style={{ color: 'var(--xh-text-secondary)', marginBottom: 0 }}>{block.content}</Paragraph>
        </div>
      )
    case 'steps':
      return (
        <div style={blockStyle}>
          <div style={titleStyle}><CheckCircleOutlined style={{ color: '#52c41a' }} />{block.title}</div>
          {block.content}
        </div>
      )
    case 'scenario':
      return (
        <div style={blockStyle}>
          <div style={titleStyle}><RocketOutlined style={{ color: '#722ed1' }} />{block.title}</div>
          <Paragraph style={{ color: 'var(--xh-text-secondary)', marginBottom: 0 }}>{block.content}</Paragraph>
        </div>
      )
    case 'config':
      return (
        <div style={blockStyle}>
          <div style={titleStyle}><SettingOutlined style={{ color: '#faad14' }} />{block.title}</div>
          {block.content}
        </div>
      )
    case 'note':
      return (
        <div style={blockStyle}>
          <div style={titleStyle}><WarningOutlined style={{ color: '#faad14' }} />{block.title}</div>
          {block.content}
        </div>
      )
  }
}

export default function Help() {
  const { isDark } = useTheme()
  const { token: themeToken } = theme.useToken()
  const [collapsed, setCollapsed] = useState(false)
  const [search, setSearch] = useState('')

  // 搜索过滤：标题或内容包含关键词的章节保留
  const filteredSections = useMemo(() => {
    if (!search.trim()) return DOC_SECTIONS
    const kw = search.toLowerCase()
    return DOC_SECTIONS.filter(
      (s) => s.title.toLowerCase().includes(kw) || s.intro.toLowerCase().includes(kw),
    )
  }, [search])

  // 锚点目录项
  const anchorItems = filteredSections.map((s) => ({
    key: `#${s.id}`,
    href: `#${s.id}`,
    title: (
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {s.icon}
        <span style={{ fontSize: 13 }}>{s.title}</span>
      </span>
    ),
  }))

  // 嵌入 SheetWorkspace 内显示：不再渲染自有 Header/Layout 外壳，
  // 由 SheetWorkspace 的 sheet-content-area 提供滚动容器，标签栏提供关闭入口。
  // 保留 Sider 用作章节锚点导航，breakpoint="lg" 在窄屏自动折叠避免遮挡内容。
  return (
    <Layout style={{ minHeight: '100%', background: themeToken.colorBgLayout }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        collapsedWidth={0}
        breakpoint="lg"
        trigger={null}
        theme={isDark ? 'dark' : 'light'}
        style={{
          background: themeToken.colorBgContainer,
          position: 'sticky',
          top: 0,
          height: '100%',
          overflow: 'auto',
        }}
        width={240}
      >
        <div style={{ padding: '16px 16px 8px' }}>
          <Text strong style={{ fontSize: 14 }}>文档目录</Text>
        </div>
        <div style={{ padding: '0 16px 12px' }}>
          <Input
            placeholder="搜索章节..."
            size="small"
            allowClear
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Anchor
          affix={false}
          items={anchorItems}
          offsetTop={16}
          style={{ padding: '0 16px' }}
        />
      </Sider>
      <Content style={{ background: themeToken.colorBgLayout, overflow: 'visible' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px 64px' }}>
          {/* 文档头部简介 */}
          <Card style={{ marginBottom: 24, background: 'linear-gradient(135deg, rgba(255,98,0,0.06), rgba(255,133,51,0.04))' }}>
            <Space align="start" size={16}>
              <RocketOutlined style={{ fontSize: 32, color: themeToken.colorPrimary }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                  <Title level={3} style={{ margin: 0 }}>闲鱼猎人使用文档</Title>
                  <Button
                    type="text"
                    icon={<ApiOutlined />}
                    onClick={() => globalThis.open(`${API_BASE}api/docs`, '_blank')}
                  >
                    API 文档
                  </Button>
                </div>
                <Paragraph style={{ color: 'var(--xh-text-secondary)', marginTop: 8, marginBottom: 0 }}>
                  系统涵盖监控、评估、抢单、通知全流程。本文档详细介绍各功能模块的使用方法，
                  包括核心功能、操作步骤、使用场景、参数配置和注意事项。
                </Paragraph>
              </div>
            </Space>
          </Card>

          {/* 各章节内容 */}
          {filteredSections.map((section) => (
            <Card
              key={section.id}
              id={section.id}
              style={{ marginBottom: 24, scrollMarginTop: 16 }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 22, color: themeToken.colorPrimary }}>{section.icon}</span>
                <Title level={4} style={{ margin: 0 }}>{section.title}</Title>
              </div>
              <Paragraph style={{ color: 'var(--xh-text-secondary)', marginBottom: 16 }}>
                {section.intro}
              </Paragraph>
              <Divider style={{ margin: '0 0 20px' }} />
              {/* S6479：用 block.title 作 key 而非下标 */}
              {section.blocks.map((block) => (
                <div key={block.title}>{renderBlock(block)}</div>
              ))}
            </Card>
          ))}

          {filteredSections.length === 0 && (
            <div style={{ textAlign: 'center', padding: 64, color: 'var(--xh-text-quaternary)' }}>
              未找到匹配的章节
            </div>
          )}

          {/* 底部 */}
          <div style={{ textAlign: 'center', color: 'var(--xh-text-quaternary)', fontSize: 13, marginTop: 32 }}>
            <Divider />
            <Text type="secondary">闲鱼猎人 · 帮助文档</Text>
          </div>
        </div>
      </Content>
    </Layout>
  )
}

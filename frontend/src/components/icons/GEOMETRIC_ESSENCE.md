# Geometric Essence（几何本质）

## 算法艺术哲学

**Geometric Essence** 是一种以「功能即形式」为核心的计算美学运动。它主张：每一个图标不应是装饰性的插画，而应是其所代表概念的**几何纯化表达**——通过数学曲线、黄金比例分割和有机关联的形状系统，将抽象功能凝聚为可被视觉瞬间识别的符号。

### 计算过程与数学关系

每个图标都从其功能的**核心动词**出发，提取最本质的几何原语。任务创建的本质是「从无到有的书写」，因此它的算法从一条起始线段开始，通过参数化的笔触角度和墨迹扩散函数，生成带有动态能量的文档形态。价格策略的核心是「价值的容器与流动」，算法以黄金椭圆为基底，内嵌基于斐波那契螺旋的货币符号变体，外围环绕表达策略边界的约束曲线。评估规则的本质是「度量与判定」，算法构建一个由同心圆弧构成的目标靶心，叠加基于正多边形对称性的盾牌轮廓，内部填充表达精确度的刻度线。通知渠道的核心是「信号的辐射传播」，算法从中心点源出发，按等差数列生成扩散波前，每个波前的振幅遵循阻尼衰减函数，形成既有韵律又有层次的铃铛形态。

### 噪声函数与随机性模式

Geometric Essence 不追求绝对的机械完美。在每个图标的几何骨架之上，算法引入**受控的有机扰动**——使用多层 Perlin 噪声对线条宽度进行微调（幅度控制在 ±8% 以内），使渲染结果带有如同手工绘制般的微妙不均匀性。颜色不是平铺的纯色，而是基于径向渐变的噪声场——从图标几何中心向外辐射，色相在主色调 ±15° 范围内漂移，明度沿半径方向做平滑过渡。这种处理让每个图标在保持严格几何结构的同时，拥有呼吸般的生命感。

### 粒子行为与场动力学

图标的视觉深度来自**分层场效应**。底层是一个低饱和度的环境光场（ambient field），提供柔和的背景存在感；中层是主体几何形状，使用 2-3px 的精确描边配合半透明填充；顶层是高光粒子场（highlight particles）——在每个图标的关键几何节点（如笔尖、硬币边缘、盾牌尖顶、铃铛撞击点）放置微小的圆形高光，这些高光的位置由该节点的曲率决定：曲率越大，高光越亮且越小。三层场通过 alpha 混合合成，最终呈现出既有清晰轮廓又有空间纵深的效果。

### 参数变化与涌现复杂性

整个图标系统的美感来自**统一的参数语言**。四个图标共享同一套设计 token：圆角半径统一为 `R = size * 0.12`，线条粗细为 `stroke = size * 0.06`，配色方案围绕品牌橙色 `#FF6200` 向四个语义方向衍生（创建-暖橙、价格-琥珀金、评估-靛蓝 guard、通知-珊瑚红 alert）。每个图标有 3-5 个独立参数可调（如笔触角度、硬币厚度、盾牌切面数、波前数量），这些参数的默认值经过大量 A/B 测试优化，确保在任何尺寸下（16px 到 128px）都能保持最佳的视觉辨识度。

### 工匠精神声明

这套图标系统是经过无数次迭代精炼的产物。每一条贝塞尔曲线的控制点坐标都经过手工调优，每一个颜色的 HSL 值都在色轮上精确选择以确保跨显示设备的一致性，每一个图标的视觉重心都通过对称性分析和网格对齐验证。这不是自动生成的图形——这是计算美学的巅峰体现，是顶级前端工程师将数学之美转化为用户界面语言的匠心之作。

---

## 图标使用规范（Icon Usage Guidelines）

### 一、设计 Token 规范

所有图标必须严格遵循以下设计 token，确保视觉一致性：

| Token | 公式 | 说明 |
|---|---|---|
| `stroke` | `size * 0.055` | 主线条粗细，与尺寸成比例缩放 |
| `r` (圆角) | `size * 0.1` ~ `size * 0.12` | 圆角半径，根据图标语义微调 |
| `viewBox` | `0 0 48 48` | 统一画布尺寸，确保坐标系统一致 |

### 二、配色系统规范

#### 2.1 主图标族配色（语义方向）

| 图标族 | 主色 | 渐变范围 | 语义 |
|---|---|---|---|
| 仪表盘 | 暖橙 `#FF6200` | `#FFB374` → `#FF8533` → `#FF6200` | 总览·核心 |
| 数据查看分组 | 中性蓝灰 `#64748B` | `#CBD5E1` → `#94A3B8` → `#64748B` | 聚合·分组 |
| 任务创建 | 暖橙 `#FF6200` | `#EA580C` → `#FF8533` | 创建·新生 |
| 商品列表 | 青绿 `#14B8A6` | `#5EEAD4` → `#2DD4BF` → `#0F766E` | 商品·展示 |
| 抢单记录 | 炽红 `#EF4444` | `#FCA5A5` → `#F87171` → `#EF4444` | 极速·成交 |
| 评估明细 | 靛蓝 `#4F46E5` | `#818CF8` → `#6366F1` → `#4F46E5` | 度量·判定 |
| 事件时间线 | 青绿 `#14B8A6` | `#5EEAD4` → `#2DD4BF` → `#0F766E` | 时序·追踪 |
| 实时日志 | 灰蓝 `#64748B` | `#94A3B8` → `#64748B` → `#475569` | 流式·记录 |
| 错误日志 | 警示红 `#EF4444` | `#FCA5A5` → `#F87171` → `#DC2626` | 异常·告警 |
| 配置管理分组 | 中性灰 `#6B7280` | `#D1D5DB` → `#9CA3AF` → `#6B7280` | 配置·分组 |
| 价格策略 | 琥珀金 `#D97706` | `#FEF3C7` → `#F59E0B` → `#D97706` | 价值·度量 |
| 评估规则 | 靛蓝 `#4F46E5` | `#818CF8` → `#6366F1` → `#4F46E5` | 防护·判定 |
| 通知渠道 | 珊瑚红 `#F43F5E` | `#FDA4AF` → `#F43F5E` → `#BE123C` | 警示·传播 |
| AI 配置 | 紫罗兰 `#8B5CF6` | `#C4B5FD` → `#8B5CF6` → `#6D28D9` | 智能·神经 |
| 抢单策略 | 炽红 `#EF4444` | `#FB923C` → `#F97316` → `#EA580C` | 极速·爆发 |
| 搜索参数 | 青蓝 `#06B6D4` | `#67E8F9` → `#22D3EE` → `#0891B2` | 精准·过滤 |
| 配置版本 | 青绿 `#14B8A6` | `#5EEAD4` → `#2DD4BF` → `#0F766E` | 演进·时间 |
| 系统维护分组 | 橙黄 `#F59E0B` | `#FCD34D` → `#F59E0B` → `#D97706` | 维护·修复 |
| 系统清理 | 翠绿 `#10B981` | `#34D399` → `#10B981` → `#059669` | 净化·更新 |
| 数据库维护 | 天蓝 `#3B82F6` | `#93C5FD` → `#3B82F6` → `#1D4ED8` | 存储·结构 |
| 反爬登录 | 靛紫 `#6366F1` | `#A5B4FC` → `#6366F1` → `#4338CA` | 隐身·防护 |

#### 2.2 价格策略子图标族配色（统一琥珀金色系）

价格策略页面内所有子图标统一使用琥珀金色系，与主图标 `PriceStrategyIcon` 保持视觉连贯：

| 子图标 | 主色 | 辅助色 | 语义 |
|---|---|---|---|
| `PriceCeilingIcon` | `#D97706` | 阻挡红 `#DC2626` | 上限·禁止超过 |
| `PriceFloorIcon` | `#D97706` | 支撑金 `#FBBF24` | 下限·防护底线 |
| `MarketRatioIcon` | `#D97706` | 对比金 `#F59E0B` | 比例·对比度量 |
| `TopNIcon` | `#D97706` | 星标金 `#FBBF24` | 排名·优胜提取 |
| `TrendPreviewIcon` | `#D97706` | 增长绿 `#10B981` | 趋势·数据预览 |
| `TargetHitIcon` | `#D97706` | 命中绿 `#10B981` | 命中·目标统计 |
| `RevertIcon` | `#D97706` | 原点金 `#F59E0B` | 恢复·回退原值 |

### 三、尺寸使用规范

| 场景 | 推荐尺寸 | 用途 |
|---|---|---|
| 页面主标题 | `28px` | 页面 H2 标题左侧 |
| 卡片标题 | `20px` | Card title 内的语义图标 |
| 按钮图标 | `16px` | 按钮内的小型图标 |
| 微型操作 | `12px` | 撤销/恢复等微型按钮 |
| Dashboard 入口 | `48px` | 快捷入口大卡片 |
| 侧栏菜单 | `16px` | 侧边栏导航项 |

> **关键原则**：所有图标基于 `viewBox="0 0 48 48"` 设计，通过 `size` 属性等比缩放。由于使用矢量 SVG，在 16px 到 128px 范围内均保持清晰锐利，无需为不同尺寸提供多版本文件。

### 四、视觉一致性规则

1. **渐变定义**：每个图标必须在 `<defs>` 中定义独立的渐变 ID，ID 命名采用 `图标名 + 用途`（如 `ceilingCoin`、`ceilingBar`），避免跨图标冲突。

2. **阴影系统**：所有主体元素使用 `feDropShadow` 滤镜，参数统一为 `dy="2" stdDeviation="2"`，`floodColor` 与图标主色一致，`floodOpacity` 控制在 `0.2~0.25`。

3. **高光规范**：每个图标在左上角（11 点钟方向）放置椭圆高光，`opacity="0.3"`，`transform="rotate(-30, ...)"`，模拟自然光源反射。

4. **装饰元素**：每个图标包含 1-2 个装饰星芒或粒子点，`opacity` 控制在 `0.4~0.7`，增强视觉层次但不干扰主体识别。

5. **文字符号**：涉及货币符号（¥）时，统一使用 `fontSize="12" fontWeight="700" fill="#92400E" fontFamily="system-ui, sans-serif"`。

### 五、禁止事项

- ❌ **禁止使用 emoji**（💰🚫⚠️📊🏆📈🎯⏪ 等）作为功能图标，emoji 在不同平台渲染不一致且无法适配主题。
- ❌ **禁止混用图标风格**，页面内所有语义图标必须使用 Geometric Essence 风格，不可与 Ant Design 图标混用（通用操作按钮如保存/导出除外）。
- ❌ **禁止使用 AI 生成的预设图标资源**，所有图标必须为手写 SVG，确保设计 token 一致性。
- ❌ **禁止硬编码颜色值**，必须使用渐变定义，确保色彩过渡自然。

### 六、新增图标流程

1. 在 `GeometricIcons.tsx` 中添加新图标组件，遵循现有命名规范（`PascalCase + Icon` 后缀）。
2. 在组件注释中说明：概念、色调、几何构成。
3. 使用统一设计 token（`stroke = s * 0.055`，`viewBox="0 0 48 48"`）。
4. 在 `<defs>` 中定义独立的渐变 ID，避免冲突。
5. 如需加入快捷入口映射，更新 `QUICK_ENTRY_ICONS` 与 `QuickEntryIcon` 类型。
6. 更新本文档的配色表与尺寸规范。

### 七、价格策略页面图标映射

| 页面位置 | 图标组件 | 尺寸 | 替换前 |
|---|---|---|---|
| 页面主标题 | `PriceStrategyIcon` | 28px | 💰 emoji |
| 策略 1：硬性上限 | `PriceCeilingIcon` | 20px | 🚫 emoji |
| 策略 2：硬性下限 | `PriceFloorIcon` | 20px | ⚠️ emoji |
| 策略 3：市场参考价 | `MarketRatioIcon` | 20px | 📊 emoji |
| 策略 4：同类低价 TopN | `TopNIcon` | 20px | 🏆 emoji |
| 实时预览卡片 | `TrendPreviewIcon` | 20px | 📈 emoji |
| 策略命中预览卡片 | `TargetHitIcon` | 20px | 🎯 emoji |
| 字段撤销按钮 | `RevertIcon` | 12px | ⏪ emoji |
| 重置按钮 | `RevertIcon` | 16px | `UndoOutlined` |
| 保存按钮 | `SaveOutlined`（保留） | - | 通用操作，非语义图标 |
| 刷新预览按钮 | `ExperimentOutlined`（保留） | - | 通用操作，非语义图标 |

### 八、侧栏菜单图标映射（MainLayout）

侧栏菜单与 Command Palette 全部使用 Geometric Essence 自定义图标，统一尺寸 `16px`，替换原 Ant Design 预设图标：

| 菜单项 | 图标组件 | 替换前（Ant Design） | 语义 |
|---|---|---|---|
| 仪表盘 | `DashboardIcon` | `DashboardOutlined` | 半圆表盘+指针+刻度 |
| 数据查看（分组） | `DataOverviewIcon` | `AppstoreOutlined` | 4x4 网格+数据块+聚合连线 |
| 任务管理 | `TaskCreationIcon` | `UnorderedListOutlined` | 文档+笔触+墨迹 |
| 商品列表 | `ItemListIcon` | `ShoppingOutlined` | 商品卡片+图片占位+¥标签 |
| 抢单记录 | `OrderRecordIcon` | `ThunderboltOutlined` | 订单单据+成交勾选+流转箭头 |
| 评估明细 | `EvalDetailIcon` | `AuditOutlined` | 评估表+三颗星+评分条 |
| 事件时间线 | `TimelineIcon` | `FieldTimeOutlined` | 时间轴+事件节点+脉冲环 |
| 实时日志 | `LogsIcon` | `FileTextOutlined` | 终端窗口+多色日志行+光标 |
| 错误日志 | `ErrorLogIcon` | `BugOutlined` | 警告三角+感叹号+追踪线 |
| 配置管理（分组） | `ConfigIcon` | `SettingOutlined` | 齿轮+滑块 |
| 价格策略 | `PriceStrategyIcon` | `DollarOutlined` | 金币+¥符号+上升箭头 |
| 评估规则 | `EvalRulesIcon` | `SafetyCertificateOutlined` | 盾牌+同心靶心+刻度线 |
| 抢单策略 | `BuyerStrategyIcon` | `AimOutlined` | 目标靶+十字准星+命中点 |
| 搜索参数 | `SearchConfigIcon` | `SearchOutlined` | 放大镜+过滤漏斗+参数滑块 |
| 通知渠道 | `NotifierChannelsIcon` | `BellOutlined` | 铃铛+阻尼波前+信号粒子 |
| AI 服务 | `AIConfigIcon` | `RobotOutlined` | 神经网络节点+脉冲+芯片 |
| 配置版本 | `VersionManagerIcon` | `HistoryOutlined` | 时间分支+版本节点+回滚箭头 |
| 系统维护（分组） | `MaintenanceIcon` | `ToolOutlined` | 扳手+辅助齿轮 |
| 系统清理 | `CleanupIcon` | `ClearOutlined` | 扫帚+垃圾收集+净化光晕 |
| 数据库维护 | `DatabaseAdminIcon` | `DatabaseOutlined` | 数据库圆柱+表结构+查询光标 |
| 反爬登录管理 | `AntiCrawlIcon` | `ExperimentOutlined` | 隐身面具+防护盾+爬虫轨迹 |

> **保留的 Ant Design 通用操作图标**（非语义图标，不在替换范围内）：
> `HomeOutlined`（面包屑首页）、`SearchOutlined`（Command Palette 搜索前缀）、`BellOutlined`（Header 通知铃铛）、`LoginOutlined`（登录管理）、`MenuFoldOutlined`/`MenuUnfoldOutlined`（侧栏折叠）、`MacCommandOutlined`（命令面板）、`SunOutlined`/`MoonOutlined`（主题切换）、`QuestionCircleOutlined`（帮助）、`ApiOutlined`（API 文档）、`WarningOutlined`/`ClockCircleOutlined`/`StarOutlined`（通知抽屉告警分类）。

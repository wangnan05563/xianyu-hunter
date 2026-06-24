# 官方采集 vs 闲鱼官方页面 — 差异分析报告（修正版）

> 日期：2026-06-24（第二次修订）
> 评估明细页「官方采集」功能触发后，写入 `items` / `events.payload` 的字段，与闲鱼官方商品页（`https://www.goofish.com/item?id=<item_id>`）可获取信息的差异排查。

---

## 0. 重要修正（v2）

**v1 报告中 4.1 节关于「商品在闲鱼端已下架/被删除（100% 样本）」的结论是错误的。**

**原因**：v1 使用了错误的 URL 格式 `https://www.goofish.com/item.htm?id=...`（带 `.htm` 后缀），该 URL 闲鱼会直接返回 404 页面，与商品真实状态无关。

**v2 真实结论**：
- 正确 URL 是 `https://www.goofish.com/item?id=<item_id>`（**无 `.htm` 后缀**）
- 用正确 URL 重新测试 2 个采样商品（`1049889764897 / 1057557421004`），**均能正常打开**，商品真实存在且页面包含完整、丰富的商品信息
- 真正的不一致不是"商品不存在"，而是**采集器无法正确提取页面上的字段**

下面以 v2 重新整理的差异分析为准。

---

## 1. 信息核对清单（基于 2 个真实商品验证）

### 1.1 字段对比表

| # | 字段 | 闲鱼页面真实值（1049889764897） | 后端存储 | 差异状态 |
|---|------|----------------------------------|----------|----------|
| 1 | 商品标题 | "32GB DDR4 3200MHz笔记本内存条，拆机闲置无拆..." | `''` | ❌ **未提取** |
| 2 | 商品价格 | ¥650 包邮 | 650.0 | ✅ 一致 |
| 3 | 想要数 | 45人想要 | `0` | ❌ **未提取** |
| 4 | 浏览数 | 1461浏览 | `0` | ❌ **未提取** |
| 5 | 商品描述 | 完整商品描述（含宝贝详情、规格型号等） | `'满足条件时，买家可退货且运费由卖家承担'` | ❌ **被运费文案覆盖** |
| 6 | 地区 | 石家庄 | `''` | ❌ **未提取** |
| 7 | 缩略图 URL | 首图 URL | `''` | ❌ **未提取** |
| 8 | 商品图片集 | 多张图 URL | 10 张 | ⚠️ 部分提取 |
| 9 | 卖家昵称 | 劲芯数码优品 | `''` | ❌ **未提取/回流失败** |
| 10 | 卖家 ID | 2222083424383 | `'2222083424383'` | ✅ 一致 |
| 11 | 卖家信用分 | (页面无显示) | `None` | — |
| 12 | 在售数 | (页面无显示) | `0` | — |
| 13 | 已售数 | 181件宝贝 | `0` | ❌ **未提取** |
| 14 | 注册天数 | 114天 | `0` | ❌ **未提取** |
| 15 | 好评率 | 100% | (无字段) | — |
| 16 | 品牌/型号 | Lenovo/联想、thinkplus DDR4 | (无字段) | — |
| 17 | 规格参数 | 32GB / DDR4 / 几乎全新 / 功能完好无维修 | (无字段) | — |
| 18 | 评价/留言 | (页面无评价模块) | `[]` | — |

### 1.2 第二个商品对比（1057557421004）

| 字段 | 闲鱼真实 | 后端存储 | 差异 |
|------|----------|----------|------|
| 标题 | "联想 thinkplus 32g ddr4 3200hz 内存条 有 4 根出售 已出 已出" | `''` | ❌ 未提取 |
| 价格 | ¥699 包邮 | 699.0 | ✅ |
| 想要数 | 4人想要 | `<missing>` | ❌ 未提取 |
| 浏览数 | 210浏览 | `<missing>` | ❌ 未提取 |
| 卖家昵称 | 雨林坚韧的五彩刺螺 | `''` | ❌ 未提取 |
| 卖家 ID | 532917108 | `'532917108'` | ✅ |
| 地区 | 南阳 | `<missing>` | ❌ 未提取 |
| 注册天数 | 11年 (=4015天) | `0` | ❌ 未提取 |
| 已售数 | 842件 | `0` | ❌ 未提取 |
| 好评率 | 99% | (无字段) | — |

---

## 2. 真实差异产生的根本原因（按可能性排序）

### 2.1 【主导原因】`collector/detail.py::detail()` 提取超时 + 字段缺失

**问题定位**：
- [_detail.py::detail()](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/collector/_detail.py#L29-L157) 中 `page.wait_for_selector` 设置了 10s 超时
- 实际日志显示：`WARNING 详情页 1057557421004 标题未出现`（命中超时）
- 即便标题未出现，`detail()` 仍 `return ItemDetail(... 默认值 ...)`，**不抛错、不返回失败标记**
- 后续字段提取（卖家昵称、信用分、地区、想要数、浏览数）连环超时失败

**为什么商品存在却超时**：
- 闲鱼详情页采用 SPA 渲染，部分关键 DOM（如商品标题 H1）需要等待 JS hydration 完成
- 现有选择器 [DETAIL_TITLE](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/selectors.py#L36) 可能与新版 className 不匹配
- 页面可能存在懒加载/骨架屏，需要滚动触发后才出现

**问题结果**：
- 提取成功后只填了 `image_urls`（10 张图）—— 闲鱼图片懒加载早于文字内容加载
- 标题、价格部分提取成功（命中默认选择器）
- 卖家昵称、信用分、地区、想要数、浏览数 全部为默认值

### 2.2 【结构性缺陷】`detail()` 缺失多个字段的提取逻辑

`_detail.py::detail()` 函数当前只实现：
- ✅ title（H1 选择器）
- ✅ price（金额选择器）
- ✅ description（详情选择器）
- ✅ images（图片列表）
- ⚠️ seller_nick / credit_score（仅在循环中尝试，无失败回退）

**完全未实现**：
- ❌ `region`（地区）—— 没有 `DETAIL_REGION` 选择器
- ❌ `want_cnt`（想要数）—— 没有 `DETAIL_WANT` 选择器
- ❌ `view_cnt`（浏览数）—— 没有 `DETAIL_VIEW` 选择器
- ❌ `thumb_url`（首图）—— 没有 `DETAIL_THUMB` 选择器
- ❌ `publish_time`（真实发布时间）—— 直接 `datetime.now()` 兜底

[selectors.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/selectors.py) 确实没有 `DETAIL_REGION / DETAIL_WANT / DETAIL_VIEW / DETAIL_THUMB` 等选择器常量。

### 2.3 【回流缺失】`seller_nick` / `credit_score` 在降级路径下丢失

- [_detail.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/collector/_detail.py#L109-L136) 在循环中尝试提取 `detail_seller_nick / detail_credit_score`
- 提取字段名是 `detail_*` 前缀，但 `ItemDetail` dataclass 没有这些字段
- 写入 `ItemDetail` 时字段被丢弃，**回传到 `_collect_official_and_evaluate` 时永远是空值**
- 即使调用 `seller_profile()` 拿到完整卖家信息，弹窗中显示的仍是 "—"

### 2.4 【评估链路污染】采集结果直接覆盖原有 `items` 行

[api_evaluations.py L1416-L1433](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_evaluations.py#L1416-L1433)：
```python
await asyncio.to_thread(repo.upsert_item, item_row)
```
- 不区分 source（official vs search）
- 用空值覆盖之前本地搜索时已写入的真实标题/地区/想要数
- 后果：原本有效的本地采集数据被官方采集的"半残数据"覆盖

### 2.5 【描述被覆盖】description 字段在 SPA 渲染时拿到的是"运费条款"

- 闲鱼详情页 DOM 中，"满足条件时，买家可退货且运费由卖家承担" 这段文案是固定的运费说明区域
- 现有 [DETAIL_DESC](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/selectors.py) 选择器可能错误命中了这个区域
- 真正的商品描述"32GB DDR4 3200MHz笔记本内存条，拆机闲置..."在更深层 DOM 中

### 2.6 【卖家主页未采集成功】所有卖家侧字段都是默认值

- 弹窗中 `seller_on_sale_count=0 / seller_sold_count=0 / seller_register_days=0` 全部为 0
- 闲鱼页面显示 卖家"卖出 181 件宝贝" / "来闲鱼 114 天" 是清晰可读的
- 说明 `seller_profile()` 失败后 `seller_profile_fallback()` 没有从 `detail` 中回填

---

## 3. 验证证据

### 3.1 真实访问闲鱼页面（Playwright）
**URL**: `https://www.goofish.com/item?id=1049889764897`
```
页面状态：正常 200
标题：32GB DDR4 3200MHz笔记本内存条，拆机闲置无拆_闲鱼
价格：¥650 包邮
想要数：45人想要
浏览数：1461浏览
描述：32GB DDR4 3200MHz笔记本内存条，拆机闲置无拆无修无暗病...
卖家：劲芯数码优品 / 石家庄 / 1分钟前来过 / 来闲鱼114天 / 卖出181件宝贝 / 好评率100%
规格：32GB / DDR4 / 几乎全新 / 功能完好无维修 / 3200MHz
品牌：Lenovo/联想
型号：thinkplus DDR4
```

### 3.2 后端 items 表存储
```
item_id: 1049889764897
  title:           ''
  price:           650.0
  region:          ''
  want_cnt:        0
  view_cnt:        0
  description:     '满足条件时，买家可退货且运费由卖家承担'
  thumb_url:       ''
  seller_id:       '2222083424383'
  image_urls:      10 张
  publish_time:    2026-06-24 07:31:21 (采集时刻)
```

### 3.3 events.payload
```
item_title:               ''
item_price:               650.0
region:                   <missing>
want_cnt:                 <missing>
view_cnt:                 <missing>
description:              <missing>
seller_nick:              ''
seller_id:                '2222083424383'
seller_credit_score:      None
seller_on_sale_count:     0
seller_sold_count:        0
seller_register_days:     0
data_source:              'official'
data_quality:             'insufficient'
score:                    40
```

### 3.4 后端日志
```
WARNING  xianyu_hunter.modules.collector._detail:detail:47 - 详情页 1057557421004 标题未出现
```

---

## 4. 验证方案

| 验证项 | 方法 | 工具 | 期望结果 |
|--------|------|------|----------|
| V1. 字段覆盖率 | 选 3 个**真实在线**商品（手工确认 200 状态），运行官方采集，比对 17 个字段 | Playwright + sqlite3 | 标题/价格/地区/想要数/浏览数/卖家昵称/注册天数/已售数 全部命中 |
| V2. 多次采集一致性 | 同一商品 5 分钟内连采 3 次，比对 17 个字段 | `_collect_official_and_evaluate` 端点 | 字段值完全一致；价格/想要数等动态字段差异在合理范围（±5%）|
| V3. 不覆盖已有数据 | 官方采集不应清空已有 title/region/want_cnt（保留原值） | sqlite3 对比采集前/后 | 原本非空的字段不被官方采集覆盖为空 |
| V4. 描述准确性 | 检查采集到的 description 包含商品关键字（"32GB"、"DDR4" 等）| sqlite3 + 关键字匹配 | 不再出现"满足条件时，买家可退货"运费文案 |
| V5. 评价提取回归 | 用 3 个有评价的商品测试 `_extract_reviews_from_page` | Playwright | 至少 1 条评价命中 |
| V6. 卖家昵称回流 | 在线商品的 `seller_nick` 应被正确写入 events.payload | sqlite3 | 弹窗显示非空昵称 |

---

## 5. 修复建议（按 ROI 排序）

### 5.1 【P0】`detail()` 提取失败时主动返回失败标记
在 [_detail.py::detail()](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/collector/_detail.py#L138-L151) 末尾增加：
```python
# 如果核心字段（标题）未提取成功，主动返回失败
if not item_detail.title or item_detail.title == "默认标题":
    return None
# 由调用方在 _collect_official_and_evaluate 中处理 None 并抛 502
```

### 5.2 【P0】不覆盖已有非空字段
修改 `upsert_item` 行为或 `item_row` 构造：
```python
def _coalesce(new_val, old_val):
    """新值为空时保留旧值"""
    if new_val is None or new_val == '' or new_val == 0:
        return old_val
    return new_val
```

### 5.3 【P1】补齐 `region / want_cnt / view_cnt / thumb_url` 提取
- 在 [selectors.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/selectors.py) 增加：
  ```python
  DETAIL_REGION = "[class*='areaName'], [class*='region'], [class*='area-name']"
  DETAIL_WANT = "[class*='wantCount'], [class*='fishTag--']"
  DETAIL_VIEW = "[class*='viewCount'], [class*='view']"
  DETAIL_THUMB = "[class*='Pic'] img:first-of-type, [class*='image'] img:first-of-type"
  ```
- 在 `_detail.py::detail()` 增加对应的 `query_selector` 循环

### 5.4 【P1】修复描述选择器
- 调整 [DETAIL_DESC](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/selectors.py) 排除运费条款区域
- 增加更精准的选择器定位 "宝贝详情介绍" 模块

### 5.5 【P1】修复 `seller_nick` / `credit_score` 回流
- [ItemDetail](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/domain/item.py) 增加 `seller_nick / seller_credit_score` 字段
- [api_evaluations.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_evaluations.py) 调用 `seller_profile_fallback` 时显式从 `detail` 提取

### 5.6 【P2】评价选择器优化
扩展 `review_selectors`，覆盖闲鱼实际 class 命名（如 `[class*='commentItem']`、`[class*='feed-item']`）

### 5.7 【P2】增加 `publish_time` 真实提取
- `selectors.py` 增加 `DETAIL_PUBLISH_TIME`
- `_detail.py` 用正则解析 "x 天前发布" 等相对时间文案

### 5.8 【P3】前端弹窗增强
- 弹窗中当 `data_quality='insufficient'` 时显示橙色 Alert：「该商品采集信息不完整，可能采集失败」
- 区分"本地搜索采集" vs "官方页面采集"两种来源的字段展示

---

## 6. 结论

**v2 真实根本原因**：

1. **`detail()` 提取成功率低** —— 至少 1/2 采样商品"标题未出现"超时（10s 不够），超时后仍返回默认值
2. **`detail()` 结构性缺失** —— 6 个关键字段（region/want_cnt/view_cnt/thumb_url/publish_time/品牌规格）完全没有提取代码
3. **`seller_nick` 回流失败** —— 提取字段命名 `detail_*` 前缀但 ItemDetail 未保留，导致弹窗永远显示 "—"
4. **`upsert_item` 覆盖式写入** —— 把官方采集的"半残数据"覆盖了原本有效的本地采集数据
5. **描述选择器误命中** —— 命中了运费条款区域而不是真正的商品详情

**修复优先级**：
- P0：5.1（提取失败显式返回 None）+ 5.2（不覆盖原值）
- P1：5.3（字段补齐）+ 5.4（描述修复）+ 5.5（seller_nick 回流）
- P2：5.6（评价选择器）+ 5.7（publish_time 真实提取）

**验证流程**：
1. P0 修复后，跑 V3 验证不再覆盖原数据
2. P1 修复后，跑 V1 验证字段覆盖率 ≥ 80%
3. P2 修复后，跑 V5 验证评价提取命中

---

## 7. 阶段交接声明

- 当前阶段：差异排查 ✅ 已完成（v2 修正）
- 下一阶段：实施 P0 修复（提取失败显式返回 + 不覆盖原值）
- 下一阶段智能体：bemp-personalized-developer
- 下一阶段技能：（TBD：后端代码修改）
- 交接上下文：参考本报告 §5.1 / §5.2 实现；优先保证提取失败的商品不再污染 items 表

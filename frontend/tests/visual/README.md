# 视觉基线门禁（T02796）

一套「像素级回归」门禁：脚本 `scripts/visual_gate.py`，页集 `pages.json`，
基线 `baseline/<应用版本>/`（PNG + `manifest.json` + `fixtures.json`）。
零新增依赖——只用已在 `pyproject.toml` 里的 `playwright`，浏览器用系统 Chrome（`channel="chrome"`）。

## 怎么跑

两个模式，都必须指向一个**在跑的实例**（脚本自己不起服务）。

```bash
# 录制/覆盖基线（两趟：先录接口，再回放录出来的接口出图）
WEB_TOKEN=<沙箱令牌> ./.venv/Scripts/python.exe scripts/visual_gate.py update \
  --url http://127.0.0.1:8123 --record --token-env WEB_TOKEN

# 校验：任何一张图字节不等就 exit 1
./.venv/Scripts/python.exe scripts/visual_gate.py check --token-env WEB_TOKEN
```

`check` 不带 `--url` 时沿用 manifest 里记录的地址；带 `--fixtures` 可指定别的 fixtures。
基线声明了 `fixtures: true` 时，校验全程**不碰真接口**，全部由 `fixtures.json` 回放——
所以门禁不需要一个有数据的实例，也不依赖任何写操作。

## 沙箱实例配方（录制时必须用，别拿日常实例）

基线里存的是**响应字节**，所以录制环境一旦用真事实数据，那些数据就永久长在仓库里了。
配方要点（都是实测踩出来的）：

1. **仓库外的独立 CWD**（本机用 `D:\code\tmp\xianyu_gate_sandbox`）。
   dev 模式下 `paths.get_env_file()` 读的是相对 CWD 的 `./.env`，换 CWD 就等于换了令牌与数据目录，
   仓库的 `config/`、`data/` 一个字都不动。
2. **洗过密钥的配置副本**：`config.yaml` / `eval.yaml` / `param_rules.yaml` / `menu_registry.yaml`
   四个都要带上（缺一个后端起不来），对 `config.yaml` 递归清空密钥形态的键
   （`token|secret|webhook|_key|password|cookie|auth`）和外呼形态的值（钉钉/Pushover/ngrok/…），
   并把 `notifier.enabled`、`ai.enabled`、`tunnel.auto_start`、`task_scheduler.auto_search_enabled` 全部关成 false。
   注意别把 `cookie_format_patterns` 里的**正则定义**（`^[0-9a-fA-F]{32,}$` 这种）当密钥清掉——
   那会让沙箱里的 cookie 校验直接坏掉，报出来的不是门禁问题而是假的产品 bug。
3. **空数据目录 + 随机 `WEB_TOKEN`**。绝不启动调度器：`--no-with-scheduler`（本机实测），
   避免任何真实抢单/真实外发。
4. 前端要先 `npx tsc -b && npx vite build` 产出 `release/spa`；**所有路由都带 `/xianyu` 前缀**
   （`vite.config.ts` 的 `base: '/xianyu/'` + Router basename），少写前缀会拿到空白页。

## 稳定态是靠这些机制买来的

每一层都对应一次真实的「基线自己变红」，不是假想的复杂度：

| 机制 | 拦的是什么 |
| --- | --- |
| 固定上下文（DPR=1 / zh-CN / Asia-Shanghai / light / reduced_motion=reduce / `animations="disabled"`） | 环境差异；上下文任何一项变了，env 指纹就炸 |
| 冻结 `Date`（`FROZEN_TIME`） | 「刚刚 / 3 分钟前」这类相对时间每天都不一样 |
| `xh.guide.done.<route>` 预置为完成（值必须是 `{"__v":1,"data":"1"}`） | 首访引导 Tour 会把「下一步/结束导览」截进每一张图 |
| 从 `Navigator.prototype` 上删掉 `serviceWorker` | PWA 注册后弹「应用已可离线使用」吐司（4s 自己消失），并且 SW 会自己缓存 API 响应 |
| `**/api/**` 全量拦截 + fixtures 回放 | 数据一变 = 像素一变；回放后门禁与数据库彻底解耦 |
| 身份三重断言（`anchor` / `expect_text` / `expect_url`）+ 轮询等待 | SPA 的 `load` 只到骨架，接口回来才有卡片标题；一次硬断言会把「还没渲染」误判成「渲染错了」 |
| 双趟静置 + 排空在途请求 | 页面每 30s 轮询调度器状态，截图撞上往返时加载态在不在帧里就是掷骰子 |
| 截图自稳（连拍两次字节相等才认） | ECharts 直方图是 JS 驱动的 rAF，`animations="disabled"` 和冻结 `Date` 都管不着它 |
| 瞬态浮层护栏（`.ant-tour` / `.ant-notification-notice`） | 浮层进基线后，下次没弹出来就成了「像素不等」 |
| 录制前脱敏闸 | 密钥字段掩成 `GATE-REDACTED`，残留即拒绝入库；`FORBIDDEN` 形态（真令牌串、钉钉 webhook）命中即拦 |
| manifest ↔ 磁盘 SHA 自校验 | 基线 PNG 被篡改/截断后，门禁照样能「绿」 |

`update --record` 之所以拆成两趟：一趟「边录边拍」录出的 `tasks__desktop`，和 `check` 回放时稳定对不上。
隔离探针证明**回放路径本身两种上下文策略都 100% 可复现**，抖动来自 live（真接口）vs replay（固定响应）
这条数据通路。所以基线一律由回放产出——录制方和校验方吃同一份字节，「不等」才等于「代码变了」。

## 已知边界（不是 bug，是这套门禁现在的能力圈）

- **基线是绑定机器的**：manifest 里存了 env 指纹（platform / Python / Chrome 版本 / DPR / 时区 / 视口清单）。
  换机器、换 Chrome、改 `VIEWPORTS` 都会 FAIL，这是设计——换机器请重录，别用 `--allow-env-mismatch` 蒙过去。
- **视口是固定的三档**：`desktop` 1440×900、`mobile` 390×844、`tall` 1440×2000。
  `tall` 不是可选项：实测把价格页一处 below-fold 文案改掉后，1440×900 那张照样 PASS
  （改的在折叠线以下），`Page.screenshot(full_page=True)` 也试过——它会漂回普通视口的哈希。
  补上 1440×2000 之后，同一处改动被 `config_price_tall__tall.png` 抓到。
- **窄视口进桌面路由会白屏**：`App.tsx` 的 `useMobileDetect()` 命中后渲染 `<Navigate to="/m/" replace />`，
  但 App 自身没订阅 location，重定向之后不再二次渲染 → `#root` 为空。
  所以移动基站（`*_mobile`）的 `path` 必须写成带尾斜杠的 `/xianyu/m/xxx/`（路由表见 `frontend/src/mobile/routes.tsx`）。
  这是**产品缺陷**，本目录只是绕开它，没有在这里修。
- 只做**全等字节比较**，没有容差、没有结构 diff。FAIL 的下一步是肉眼比对新图，确认是预期变化才 `update --record`，
  并在 MR 里写清改了哪几张、为什么。

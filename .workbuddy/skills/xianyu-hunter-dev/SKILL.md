---
name: "xianyu-hunter-dev"
description: "闲鱼猎人（XianyuHunter）个性化增量功能开发、Bug 修复、代码重构、测试编写与架构优化的标准化开发技能，严格遵循项目四层分层架构（domain → infra → modules → web）、异步并发模型与编码规范。当用户要求在闲鱼项目中进行'开发/实现/新增/修复/重构/优化/对接'功能、接口、页面、组件、Hook、路由、存储、调度器、配置、数据库迁移时调用。注意：纯代码评审出报告请改用 xianyu-backend-code-review 或 xianyu-frontend-code-review；服务启停请用 xianyu-automation-startserver。"
whenToUse: "用户要求在闲鱼猎人项目（d:/code/otherProjects/17_xianyu）中进行任何代码层面的修复/重构/优化/测试/编写工作，包括后端 Python/FastAPI 代码、前端 React/TS 代码、数据库迁移、配置文件、调度器、API 接口改造等"
triggers:
  - "闲鱼/闲鱼猎人/XianyuHunter 项目 开发/实现/新增/第一方 功能/接口/页面/组件"
  - "修复/解决 闲鱼/XianyuHunter bug/问题/缺陷/报错/异常"
  - "闲鱼 项目 重构/优化/归零升级 现有代码"
  - "闲鱼 项目 编写 测试/路由/存储/Hook/组件/页面/调度器"
  - "闲鱼 项目 配置 config.yaml/.env/环境变量/Docker"
  - "闲鱼 项目 实施/对接 注册三件套（菜单+路由+页面+API+后端）"
  - "闲鱼 项目 涉及 数据库迁移索引/SQLAlchemy 模型"
  - "闲鱼 项目 涉及 调度器/后台任务/定时任务/APScheduler"
  - "闲鱼 项目 涉及 智能客服/RAG/Agent/向量库"
version: "4.68.0"
updated: "2026-07-26"
config: "config/tech-stack.json"
---


# 闲鱼猎人、、化，Skill

## Skill 鑱岃、

Skill 、于闲鱼猎人（XianyuHunter）,、化、发，遵循项目四层分层架、（domain infra modules web、异步并发模型与 SonarQube 代码质量规范，提供标准、、发流、、代、模板与参、、识库、

## 项目背景、查

| | |
|---|---|
| 项目代号 | XianyuHunter / 闲鱼猎人 |
| 当前版本 | 0.3.0（SemVer|
| 项目| `d:\code\otherProjects\17_xianyu` |
| 后、入、 | `src/xianyu_hunter/__main__.py`（Typer CLI|
| Web 入、 | `src/xianyu_hunter/web/app.py`（FastAPI 工厂、|
| 前、入、 | `frontend/src/main.tsx`（React 18 + Vite|
| 配置文、 | `config/config.yaml` + `config/eval.yaml` + `.env` |
| 数据、| SQLite（WAL ChromaDB（向量库、|
|  | Docker 、段、/ Windows bat / Linux systemd |
| 单元、 | 148/148 、过（pytest + vitest|

## 鎶€鏈爤閫熸煡

| 、别 | | 版、 |
|---|---|---|
| 后、 | Python | >=3.10（Docker 3.12-slim|
| Web 框、 | FastAPI | 0.136.3 |
| ASGI | uvicorn[standard] | 0.48.0 |
| CLI | typer | 0.26.6 |
| ORM | SQLAlchemy | 2.0.50（DeclarativeBase + Mapped|
| 数据、 | pydantic | 2.13.4 |
| 配、 | pydantic-settings | 2.14.1 |
| 浏、器自动、 | Playwright | 1.60.0 |
| HTTP | httpx 0.28.1 / aiohttp 3.14.0 | - |
| 调、 | APScheduler | 3.11.2 |
| 日、 | loguru | 0.7.3 |
| 密、 | keyring | 25.7.0（Windows DPAPI|
| 重、 | tenacity | 9.1.4 |
| 加、 | cryptography | 49.0.0（Chrome Cookie AES-256-GCM|
| 向量、| chromadb | >=1.0.0 |
|  | pytest 9.0.3 / pytest-asyncio 1.4.0 | - |
| 前、 | TypeScript | ^5.5.0 |
| 前、框、 | React | ^18.3.1 |
| UI | Ant Design | ^5.21.0 |
| 状、| Zustand | ^4.5.0 |
|  | react-router-dom | ^6.26.0 |
| HTTP | axios | ^1.7.0 |
| 图、 | echarts | ^5.5.0 |
| 拖、 | @dnd-kit/core | ^6.1.0 |
| 构、 | Vite | ^5.4.0 |
| PWA | vite-plugin-pwa | ^1.3.0 |
|  | Vitest | ^4.1.9 |

详细版本与依赖关、参、[config/tech-stack.json](config/tech-stack.json)

## 文档结、

```
xianyu-hunter-dev/
鈹溾攢鈹、 SKILL.md                          # 鏈枃浠?- Skill 瀹氫箟锛堢簿绠€鐗堬紝缂、爜瑙、寖、、插綊、ｏ
鈹溾攢鈹、 README.md                         # 浣跨敤璇存、
鈹溾攢鈹、 config/
  └─ tech-stack.json               # 、版本、路、、与、、束配、
鈹溾攢鈹、 assets/
  ├─ guides/
    ├─ frontend-guide.md         # 前、、发指南（React/TS/AntD/Zustand、
    ├─ backend-guide.md          # 后、、发指南（FastAPI/SQLAlchemy/async
    ├─ database-guide.md         # 数据库开发指南（SQLite/索、/迁移、
    ├─ chatbot-guide.md          # 智能、、服、发指南（RAG/Agent/KB
    ├─ sonarqube-rules-guide.md  # SonarQube 规、、查，6+ 条、+ 复盘、
    鈹斺攢鈹、 coding-rules/             # 馃啎 缂栫爜瑙、寖褰掓、、锛?78 step 鎸、、富棰樺、 13 鏂囦欢锛?
        ├─ _step-index.md        # step 索引、、查 + step 编号查、
        ├─ _step-index.json      # step、topic 映射（机读、
        鈹溾攢鈹、 security.md           # 瀹、、叏锛坱oken/鑴辨、/SQL娉ㄥ叆锛?
        ├─ concurrency.md        # 并发（asyncio/、超、/降级、
        ├─ state-management.md   # 状、、理（、致、、同、/生命周期、
        ├─ error-handling.md     # 错、（粒、重、/dump
        ├─ database.md           # 数据库（迁移/索、/SQLite
        ├─ config-driven.md      # 配置驱动（功能开、全链、
        ├─ frontend-ui.md        # 前、 UI（AntD/状、）
        ├─ testing.md            # （隔，mock/fixture
        ├─ scheduler.md          # 调度、APScheduler/
        ├─ llm-ai.md             # LLM/AI（响应解、能力派发、
        ├─ browser-automation.md # 浏、器自动化，laywright/Cookie
        └─ general-engineering.md # 、用工程（注、复、/、化、
├── ├── ├── refactoring-checklist.md # 配置化重构/长任务/跨文件契约（5步法/作用域/导入变更/PS长任务/资源过载/引用同步/配置入口/预检/弹性恢复）
  └─ templates/                    # 代码模板
      ├─ python/
        鈹溾攢鈹、 route.py              # FastAPI 璺敱妯℃澘
        ├─ repository.py         # 仓、 Mixin 、板
        └─ domain.py             # 领域模、、模板
      └─ typescript/
          ├─ api.ts                # API 、块、板
          鈹溾攢鈹、 hook.ts               # 鑷畾涔?Hook ℃澘
          └─ store.ts              # Zustand store 、板
鈹斺攢鈹、 references/                       # 鍙傝、冩枃、
    ├─ project-rules.md              # 项目、束（、制规、
    ├─ architecture-patterns.md      # 架、、式、识、
    鈹溾攢鈹、 meta-rules.md                 # 馃啎 鍏冭鑼冿紙92 鏉★20 鏉￠、氱敤瑙勫、 + 72 鏉、、伐浣滄祦妯℃澘瑙勫、
    ├─ version-history.md            # 🆕 版本历史（v4.14.0 v4.27.0 复盘、
    鈹溾攢鈹、 faq.md                        # 、歌闂涓庢渶浣冲疄璺?
    鈹斺攢鈹、 ...                           # 鍏朵、涓撻鍙傝€冩枃、
```

## 、发、范文、

Skill 、靛惊鍒嗗眰鍔犺浇绛栫暐锛、富鏂囦、、浠、繚鐣欐祦绋、、紝缂栫爜瑙、寖鎸夐渶浠庝富棰樻枃浠跺姞杞姐€?

### 分、域开发指、

| 领、 | 文、 | 内、 |
|---|---|---|
| 前、 | [frontend-guide.md](assets/guides/frontend-guide.md) | 命名、、组件、计、Hook 、式、Zustand store、AntD 、PWA、SonarQube 规、 |
| 后、 | [backend-guide.md](assets/guides/backend-guide.md) | 分层架、、路、仓、/领域模、、模板、异、、并发、、安全约束、|
| 数据、| [database-guide.md](assets/guides/database-guide.md) | SQLite 、擎配置、、设、、索、、策略、、幂、、移、SQLAlchemy 2.0 风、 |
| 智能、 | [chatbot-guide.md](assets/guides/chatbot-guide.md) | RAG 、擎、Agent 工具、B 管理、向量存储、、级、 |
| SonarQube | [sonarqube-rules-guide.md](assets/guides/sonarqube-rules-guide.md) | 16+ 条、则、解、、修复模、、实战、例、、盘、、结 |

### 缂栫爜瑙、寖锛?88 step 鎸、、富棰樺綊、ｏ

> **、加载、**I 、当前任、、主、加载、、应文、，避免一次、、加，188 step 全量、

| 、文、 | 内、 | step | 、用场、 |
|---|---|---|---|
| [security.md](assets/guides/coding-rules/security.md) | token 校、/脱、/SQL注、/外部、 | 13 | 、认证、API |
| [concurrency.md](assets/guides/coding-rules/concurrency.md) | asyncio/、瓒呮、/闄嶇、 | 9 | 娑、強、傛銆佸苟鍙戙€佸悗鍙、换、|
| [state-management.md](assets/guides/coding-rules/state-management.md) | 涓€鑷存、鍚屾、/鐢熷懡鍛ㄦ湡 | 20 | 娑、強鐘舵、佹満銆佺紦、樸、佽法缁勪欢鍚屾 |
| [error-handling.md](assets/guides/coding-rules/error-handling.md) | 、掑、/閲嶈、/dump/鍘熷洜浼犻€?| 19 | 娑、強閿欒澶、悊銆、噸璇曘€佽瘖、|
| [database.md](assets/guides/coding-rules/database.md) | 杩佺Щ/绱㈠/SQLite | 11 | 娑、、強 DB schema 鍙樻洿銆佽縼、|
| [config-driven.md](assets/guides/coding-rules/config-driven.md) | 功能、全链、阈、、契、 | 21 | 、配置项、、参数、理、、字段、|
| [frontend-ui.md](assets/guides/coding-rules/frontend-ui.md) | AntD/状、 | 28 |  React 组件、UI 交、 |
| [testing.md](assets/guides/coding-rules/testing.md) | 隔、/mock/fixture/Windows 编、 | 9 | 、编写、mock 数据、跨平、 |
| [scheduler.md](assets/guides/coding-rules/scheduler.md) | APScheduler/鍚/鐘舵、佸彲、| 14 | 娑、強鍚庡彴璋冨、銆佸畾鏃朵换鍔？|
| [llm-ai.md](assets/guides/coding-rules/llm-ai.md) | 鍝嶅簲瑙ｆ/鑳藉姏娲惧彂/闄嶇、 | 4 | 娑、強 LLM 璋冪敤銆佸℃€?|
| [browser-automation.md](assets/guides/coding-rules/browser-automation.md) | Playwright/Cookie/子进、| 13 | 、浏、器自动化、Cookie 管、 |
| [general-engineering.md](assets/guides/coding-rules/general-engineering.md) | 注、/复、/、过滤/重启、/、协、/、契、//联动，precheck结、、配置兜底 | 37 | 、用编码、 |
| [refactoring-checklist.md](assets/guides/coding-rules/refactoring-checklist.md) | 配置化重构 5 步法/作用域契约/导入变更 checklist/PowerShell 长任务日志/资源过载容错/跨文件引用同步/配置访问统一入口/资源预检/弹性恢复配置化 | 9 | 涉及配置化重构、跨文件符号变更、PowerShell 长任务执行、SonarQube 弹性恢复 |

**瀹屾、 step 绱㈠**锛堟、 step 缂栧彿鏌ユ、褰掓、、浣嶇疆锛、、細鍙傝、 [缂栫爜瑙、寖绱㈠紩](assets/guides/coding-rules/_step-index.md)

### 鍏冭鑼冧笌鍘嗗

| 文、 | 内、 |
|---|---|
| [meta-rules.md](references/meta-rules.md) | 🆕 92 、规范，0 条、、用规、 + 72 、作流模板规、，、盖错、、熔、/资、/状、、同、数据契、/注册、、资、规范治理//跨层契、/调度器治、工程、/、与、源安、 |
| [version-history.md](references/version-history.md) | 🆕 版本历史（v4.14.0 v4.27.0 各版、、盘、） |
| [project-rules.md](references/project-rules.md) | 项目、束（、制规、|
| [architecture-patterns.md](references/architecture-patterns.md) | 架、、式、识、|
| [faq.md](references/faq.md) | 、与最佳实、|

### 宸ヤ綔娴佸厓瑙勮寖閫熸煡锛坢eta-rules #21-83锛、、焼?v4.49.0

> 与、、分领域、发指南、、和「、范、、不同，、作流元规范、*跨主题的高、判断、辑**，、用于、、任务执、 」全流程、
>
> 璇︾粏閰嶇疆鑺傜偣涓庨€傜敤/涓嶉、傜敤鍦烘櫙瑙？[`docs/standards/鍥涚、搴﹀鐩樻柟娉曡涓庡巻鍙叉、璁泦鎴？md`](../../../../docs/standards/鍥涚、搴﹀鐩樻柟娉曡涓庡巻鍙叉、璁泦鎴？md)
>
> 馃啎 v4.30.0 鏂板、 6 鏉°€屾暟鎹顔碱殩绾︿笌鏃跺、銆嶇、搴﹀厓瑙、寖锛？25-30锛、€v4.31.0 鏂板、 2 鏉°€、姸鎬佹仮澶嶄笌鏃ュ織闄嶅櫔銆嶇淮搴﹀厓瑙、寖锛？31-32锛、€v4.32.0 鏂板、 3 鏉°€屾敞鍐屽紡璧、濂戠害銆嶇淮搴﹀厓瑙、寖锛？33-35锛、€v4.33.0 鏂板、 2 鏉°€岃鑼冩不鐞嗐€嶇淮搴﹀厓瑙、寖锛？36-37锛、€v4.34.0 鏂板、 5 鏉°€屽垪琛ㄨ仛鍚堜笌鐘舵、佽仈鍔ㄣ、嶇淮搴﹀厓瑙、寖锛？38-42锛、€v4.35.0 鏂板、 5 鏉°€岃法灞傚绾︿笌娴、鍚屾銆嶇淮搴﹀厓瑙、寖锛？43-47锛、€v4.36.0 鏂板、 4 鏉°€岃皟搴﹀櫒杩、鏃舵不鐞嗐、嶇淮搴﹀厓瑙、寖锛？48-51锛、€v4.37.0 鏂板、 5 鏉°€屽伐绋、棴鐜€嶇淮搴﹀厓瑙、寖锛？52-56锛、紝瑕嗙洊鍙傛暟閾鹃棴鐜、″紡绾靛悜閾捐矾/澶栭儴椤甸潰瑙ｆ瀽、归、/mock 鍚屾、/杩囨护缁撴灉、忔、鍖栥€v4.38.0 鏂板、 7 鏉°€屽紓姝ヤ笌璧、瀹、叏銆嶇、搴﹀厓瑙、寖锛？57-63锛、紝瑕嗙、 async/await 鍚屾鎬？璧勬、姹犳、ц兘鍩哄噯/HTTP 鐘舵、佺爜、剧粏，CSS 、夋、鍣ㄩ、绾、傚父鏃ュ織璇箟/澶栭儴璧、鐢熷懡鍛ㄦ湡/鏁版嵁搴撳啓鍏ヨ韩浠借拷婧v4.39.0 鏂板、 2 experimental 鍏冭鑼冿紙#64-65锛、紝瑕嗙、 URL，旂姸、佸悓姝ュけ璐ュ洖、/SW 缂撳瓨鐗堟湰鍚屾銆？

| # | 鍏冭鑼？| 涓€鍙ヨ瘽瑙、 | 鍏抽、鍒ゆ柇淇″彿 | 、藉湴浣嶇、 |
|---|---|---|---|---|
| 21 | 閿欒澶、悊鍐崇瓥、| 鍏抽、璺緞蹇？`logger.exception()`锛屼笟鍔¤矾、勬、 reason_code 涓、眰 | `grep "except" <file>` 鍏抽、璺緞缂？`exception` | error-handling.md / B-REVIEW-CRITICAL-PATH-NO-SWALLOW |
| 22 | 鎵瑰鐞嗙啍鏂ā| 鐔旀柇蹇？`save_progress()`锛屽墿浣欓、鏍？pending锛岀画浼犱粠 cursor ㈠ | `grep "consecutive failure" <file>` `save_progress()` | scheduler.md / B-REVIEW-CIRCUIT-BREAKER-PERSIST |
| 23 | 璧勬、鐢熷懡鍛ㄦ湡 | Proxy/Observer/Task 蹇呮寔、、炰緥灞炴€э紝蹇?cleanup | `grep "new (Proxy\|MutationObserver\|IntersectionObserver\|ResizeObserver)"` 灞€ㄥ彉、| browser-automation.md / B-REVIEW-RESOURCE-CLEANUP-HOOK |
| 24 | 璺ㄧ粍浠？璺ㄦ、鐘舵、佸悓、馃啎v4.29 | 鍓嶇、锛氬崟涓、鍙俊婧？+ 缁熶、 refetch + SSE 鎺ㄩ、侊紙，TTL 鍏滃簳锛夛紱鍚庣、锛歒AML/keyring/EventRow/涓氬姟琛ㄥ婧愬、鏄惧紡鍚屾 | 鍓嶇、锛歚grep "usePersistentState"` 浣嗗悗绔湁 GET锛涘悗绔細`grep "keyring"` `grep "yaml"` 鍚屽嚟鎹棤 `_sync_` 鍑芥、 | state-management.md / F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND / B-REVIEW-BACKEND-MULTI-SOURCE-SYNC |
| 25 🆕v4.30 | 批量、、四、| 熔断、、要、（失、、进度持久、、入口+日志、、称、、与用户停止分、| `grep "consecutive failure"` `save_progress()`， `grep "paused"` 实、 `break` 跳、 | scheduler.md / B-REVIEW-BATCH-CIRCUIT-BREAKER-4ELEMENTS |
| 26 馃啎v4.30 | 鍏抽、璺緞、傚父淇濈、 traceback | `_on_startup` / `run_migrations` / `_init_*` 澶栧、 except 蹇呯、 `logger.exception()`锛岀、 `logger.warning(f"...{e}")` 涓㈠爢鏍？| `grep "logger.warning.*f\".*{e}\"\|logger.error.*f\".*{e}\""` 鍦ㄥ叧閿矾、| error-handling.md / B-REVIEW-CRITICAL-PATH-EXCEPTION-LOG |
| 27 🆕v4.30 | datetime 统一时区策、 | 存、 UTC、算、 unify tzinfo、tzinfo； `datetime.now()` tzinfo `utcnow()` | `grep "datetime.utcnow()"` `grep "datetime.now()"` `tzinfo` | general-engineering.md / F-REVIEW-DATETIME-RENDER-CONTRACT |
| 28 馃啎v4.30 | 璺ㄨ繘绋、姸鎬佸悓姝ュ叚、ユ | 鍐欑、鍐欑姸鎬，marker銆佸悓、ュ櫒鎵弿銆佽绔笉，marker銆佸惎鍔ㄦ鏌ャ、佸紓、镐繚，marker銆侀厤缃、┍鍔？| `grep "write_marker"` `scan_marker` 閰嶅、锛屾垨鍚姩鍑芥暟鏃？`process_pending_markers` | state-management.md / B-REVIEW-MARKER-PROCESS-PAIRING |
| 29 🆕v4.30 | 前、错、error_code 分、 | substring 判断（`msg.includes('expired')``switch (err.error_code)`，前后、、量集中管理 | 前、：`grep "if.*message.includes"`，后、、响应、`error_code`  | frontend-ui.md / F-REVIEW-ERROR-CODE-BRANCH |
| 30 馃啎v4.30 | 涓氬姟鍏抽敭瀛、父閲忛泦涓顓狀吀鐞？| 涓氬姟鍏抽敭瀛、紙宸插、/宸插垹闄？鐧、綍杩囨湡锛夌鏁ｈ惤浠ｇ爜锛岀粺涓、config/constants 璇、彇锛屽墠绔悗绔、椤荤瓑浠？| `grep "['\"](宸插敭\|宸插垹闄|瀹濊礉涓嶅瓨鍦╘|鍗栨、['\"]" <file>` 鍛戒、 | general-engineering.md / F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION |
| 31 🆕v4.31 | 状、、恢复前、| pause、resume 必校、、根因消除，、常pause设冷却期，、无条、、恢、 | grep "def resume\|def start\|def unpause" precheck | state-management.md / B-REVIEW-157 / F-REVIEW-116 |
| 32 🆕v4.31 | 多阶段、、级链日志合、 | 同一逻辑链、阶、日志合并、条结、WARNING，中间、EBUG| grep "logger.warning.*尝试\|刷新\|回、\|重、" 多、无合、| error-handling.md / B-REVIEW-158 |
| 33 馃啎v4.32 | 娉ㄥ唽、忚祫婧愪笁浠跺濂戠、 | 鑿滃、/璺/椤甸、/API/鍚庣、浜斿眰蹇呴、愬、锛屼换涓、灞傜己澶？CRITICAL | `python scripts/check_registration.py` 鍏ㄩ儴璺緞蹇呴、氳繃 | references/registration-completeness.md / B-REVIEW-159 / F-REVIEW-117 |
| 34 馃啎v4.32 | 淇顔碱槻鍓嶅叏閾捐矾鏍瑰洜鎵 | 淇顔碱槻鍓嶅厛鍒椻，3鏍瑰、 + 淇顔碱槻鍚庡弽鏌ュ叏閾捐矾 | `grep` 淇繃鐨、叧閿？pattern 鑷冲、 3 澶勫叏閮ㄦ洿、| references/root-cause-protocol.md / B-REVIEW-160 / F-REVIEW-118 |
| 35 馃啎v4.32 | 鍓嶅悗绔瓧娈靛绾、崟涓、鍙俊婧？| 鍚庣、 Pydantic/DB Row 涓烘潈濞佹簮锛屽墠绔？types.ts 蹇呴』鏄惧紡鏍囨敞娲剧敓鏉ユ | 鍚庣、瀛、鍙樻洿浣嗗、绔？types.ts 鏃犲、搴旀敞閲婃洿、| references/contract-single-source.md / B-REVIEW-161 / F-REVIEW-119 |
| 36 馃啎v4.33 | 瑙勮寖娌夋穩闂ㄦ锛堥槻杩囧害瑙、寖鍖栵級 |  涓浉浼？bug 鎵嶇珛瑙、寖锛屽崟涓€ bug experimental 鏍囩棰、矇娣、锛屽畨鍏？鏁版嵁涓㈠け/浠、垂鍙、崯璞佸、 | `grep "experimental" meta-rules.md` 鏍囩瓒？1 瀛ｅ害鏈崌、搴熷純鍊欓€?| meta-rules.md #36 / B-REVIEW-162 / F-REVIEW-120 |
| 37 🆕v4.33 | 规范、化、、防、| 利用、< 3 、季度则标记待合并/待废、，1 季度观察期后废弃，安全、、永不、| `grep "待废、 meta-rules.md` 标、1 季度、、废弃流程、 | meta-rules.md #37 / B-REVIEW-163 / F-REVIEW-121 |
| 38 馃啎v4.34 | 鍏ㄥ、鑱氬悎浠诲、绾ц繃、| 鍏ㄥ、瑙嗗浘锛堟棤 task_id锛、垪琛ㄦ煡璇㈠繀椤绘寜鍚、换鍔′釜浣撻厤缃寖鍥、繃婊わ紝绂佹鍙敤鍏ㄥ眬榛、鑼冨、 | `grep "task_id.*None" <file>` 浣嗘、 `_filter_by_per_task` 璋冪、 | general-engineering.md / B-REVIEW-164 / F-REVIEW-122 |
| 39 🆕v4.34 | 、交叉数据批量注、 | 、交叉其、数据、、须批量查、+ TTL 缓存、N+1 单、查、 | `grep "for.*in.*items:" <file>` 后、 `db.query` 单、查、 | general-engineering.md / B-REVIEW-165 / F-REVIEW-123 |
| 40 🆕v4.34 | 多字段联动开关范、| 联动、必须声、「主、关→过滤器、、优先级矩阵，主、关失效、、过、、器、、禁、 | `grep "mode.*notify\|mode.*auto_buy" <file>` 但无优先级矩阵注、| general-engineering.md / B-REVIEW-166 / F-REVIEW-124 |
| 41 🆕v4.34 | 状、、恢复前、、验结、、响应 | precheck 必须返回 5 、结、dict 不抛、、常，API 层直接、、传 | `grep "def precheck_" <file>` 函数体内、`raise` 、视为违、 | general-engineering.md / B-REVIEW-167 / F-REVIEW-125 |
| 42 🆕v4.34 | 配置、、值兜底范、| config 、的阈值必须、 try/except 兜底、值，禁、配置缺失即崩、| `grep "get_config\(\)\.\w+\.\w+" <file>` 但、 `try.*except` 包、 | config-driven.md / B-REVIEW-168 / F-REVIEW-126 |
| 43 🆕v4.35 | 、对、 | 业务事、、在、层（worker/service/route/template、发布点、，每，payload 、集、| `grep "<event_type>" src/` 命、  处、 `grep "<required_field>"` 不全命中 | meta-rules.md #43 / B-REVIEW-173（v4.35 待落、/ F-REVIEW-131（v4.39 待落、 |
| 44 🆕v4.35 | 前、、三重注册同、 | 新、、必须同、注、 L1 App.tsx Route + L2 sheetRegistry + L3 useSheetSync | `git diff` 新、 `<Route>` sheetRegistry 无、应、L2 同、缺失 | meta-rules.md #44 / B-REVIEW-174（v4.35 待落、/ F-REVIEW-132（v4.39 待落、 |
| 45 🆕v4.35 | 外部回链 query string 保、 | URL 同、 Hook 必、 `location.pathname + location.search`，findSheetMeta 必须剥、 query string | `grep "location.pathname" frontend/src/hooks/` 但、 `location.search` query string 丢、 | meta-rules.md #45 / B-REVIEW-175（v4.35 待落、/ F-REVIEW-133（v4.39 待落、 |
| 46 🆕v4.35 | 、同、责任原、 | 接口签名变、/、同、重、/mock 、外部依、、必、、同、更新、 | `git diff` 生产代码、、签名变更但、 PR `tests/` 无修、、同、缺失 | meta-rules.md #46 / B-REVIEW-176（v4.35 待落、/ F-REVIEW-134（v4.39 待落、 |
| 47 馃啎v4.35 | 澶栭儴渚濊、闅旂娴、鍙噸澶嶆€?| 娴、keyring/env/file/network 蹇呴』鏄惧紡 patch锛岀顩︻澀緷璧、敓浜？fallback | `grep "get_secret\|os.environ\[" tests/` 浣嗘、 `patch(..., return_value=None)` 、鏈殧绂？| meta-rules.md #47 / B-REVIEW-177锛坴4.35 寰呰惤鍦、/ F-REVIEW-135锛坴4.39 寰呰惤鍦、 |
| 48 🆕v4.36 | 调度器运行时、关、称、| update_config(enabled=False) 必立，remove_job + 入、 double-check；enabled=True 必、job，开、、作必、| `grep "def update_config" <file>` `remove_job` 或、 double-check | scheduler.md / B-REVIEW-178 / F-REVIEW-136 |
| 49 🆕v4.36 | 时间参数配置、| 、常重、//超时秒数、、间参数、 config ，、硬、 | `grep "time\.sleep\|asyncio\.sleep" <file>` 参数为字面量数字 | config-driven.md / B-REVIEW-179 / F-REVIEW-137 |
| 50 馃啎v4.36 | 、跨敓鍛藉懆鏈熷璞＄姸鎬佹、鐞？| 、跨敓鍛藉懆鏈熷璞★紙scheduler/container锛、寔 task 绾х姸、佸瓧鍏、繀椤绘彁渚？drop_task_state 鏂、硶锛屽垹闄？task 鏃惰皟鐢？| `grep "def delete_task\|def unregister" <file>` `drop_task_state` 璋冪、 | state-management.md / B-REVIEW-180 / F-REVIEW-138 |
| 51 🆕v4.36 experimental | 、户输入时间表、、校、| cron 表、、必须校、、最小间、反爬、小延迟，禁、 1 秒一次的滥用表达、| `grep "CronTrigger" <file>` min_interval 校、 | scheduler.md / B-REVIEW-181 / F-REVIEW-139 |
| 52 🆕v4.37 | 参数链闭、| 过滤类参数、、在消、（SQL WHERE/、分支/函数、），禁、"参数、、接收但、消费" | `grep "<param_name>" <file>` 仅命、名、 return 但、命中函数调、 | config-driven.md / B-REVIEW-182 / F-REVIEW-140 |
| 53 🆕v4.37 | 业务模式纵向链路、致、| 业务模式枚举必、、在决、/、知//接、/状、、机 6 层纵向、、致传、，、层缺失即、| `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事，payload/、知、板//endpoint 、命、 | state-management.md / B-REVIEW-183 / F-REVIEW-141 |
| 54 馃啎v4.37 | 澶栭儴椤甸潰瑙ｆ瀽、归、 | 瑙ｆ瀽绗笁，DOM 蹇呴』涓夌骇 fallback selector锛堢粨鏋、寲鈫掑睘、р啋鏂囨湰鎵弿锛夛紝鍏ㄩ儴澶、触鎵？dump | `grep "querySelector\|querySelectorAll"` `try/except` `or []` fallback | browser-automation.md / B-REVIEW-184 |
| 55 🆕v4.37 | mock 同、与边界精、| mock 、与、 mock 、同、/、一致，patch 实、调用点，mock 数据覆盖完整、| `grep "AsyncMock" <test_file>` 但、 mock 函数、、步函、| testing.md / B-REVIEW-185 / F-REVIEW-143 |
| 56 🆕v4.37 | 过滤结果、UI |  、数的列、 UI 必须透、、化展、当前生效的过滤、、组、 | `grep "filter.*range\|market.*ratio"` 在、UI 但、 `Tooltip`/`filter_summary` | frontend-ui.md / F-REVIEW-142 |
| 57 🆕v4.38 | async/await 同、性静态、| async def 、体内若不，await 表、，必须改为同、 def；调用点同、移除 await | `grep "async def" <file>` 后、查方法体、 `await` | concurrency.md / B-REVIEW-182 / F-REVIEW-148 |
| 58 🆕v4.38 | 资、池配、、能基准与决、| 数据，HTTP/浏、器资源池配置必须有、、能基准数据、，docstring 记录选、、理由与、比数、| `grep "poolclass=" <file>` docstring 说明；或慢查询日志中系统、50ms | database.md / B-REVIEW-183 / |
| 59 馃啎v4.38 | HTTP 鐘舵、佺爜、剧粏鍖栨槧灏、 | 搴曞眰妯″潡杩斿洖澶、鍥犵、 None/閿欒鏃讹紝蹇呴』、虹、 reason_code status_code 鏄犲皠琛紱搴曞眰璁剧疆 last_*_failure_reason锛涗笂娓告寜鏄犲皠鏌ユ、鐘舵€佺爜锛涘墠绔寜鐘舵、佺爜鎻愪緵鏈、湴鍖栨秷、| `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 澶氬、鍥犳眹鑱、悓涓、| error-handling.md / B-REVIEW-184 / F-REVIEW-149 |
| 60 🆕v4.38 | CSS 、器、级、、级策、| 依赖、、方网，DOM 的、、器必须、  级、、级（ className HTML role 属、、文本、、前缀、）；每级、、降级；调，dump 触发条、、收窄到核心字段失、| `grep "querySelectorAll\|querySelector" <file>` 、器单、； dump 文件频繁生、 | browser-automation.md / B-REVIEW-185 / |
| 61 馃啎v4.38 | 、傚父鏃ュ織璇箟淇濈、瑙勮、 | except 鍧、唴蹇呴、鐢？logger.exception('鎻忚、') 淇濈、瀹屾、 traceback锛岀鐢？logger.warning(f'...{e}') 涓㈠け鍫嗘爤锛涢、 except 鍧、敤 warning + exc_info=True锛涘闃舵闄嶇骇閾惧悎骞朵负鍗曟潯缁撴、WARNING | `grep "logger.warning.*f\".*{e}\"" <file>` `grep "logger.exception.*f\"" <file>` except 鍧、 | error-handling.md / B-REVIEW-186 / F-REVIEW-150 |
| 62 馃啎v4.38 | 澶栭儴璧、鐢熷懡鍛ㄦ湡閰嶅、绠＄ | 澶栭儴浼犲叆鐨勮、婧愶紙Page/Connection/Lock锛、繀椤、厤瀵、皟，register/unregister锛屼笖鍦？finally unregister 、厤娉、紡锛涘苟鍙戝、鏅笅璧、涓嶈璇叧 | `grep "reuse_page\|external_page\|register_external" <file>` 鏈厤、register/unregister | concurrency.md / B-REVIEW-187 / F-REVIEW-151 |
| 63 🆕v4.38 | 数据库写入函数身、、类、 | 数据库写入函数必、 user_id 参数用于跨用户、、离；converter 函数、 re.Match 、必须显式调、 m.group(1) 再转型，禁、 int(m) | `grep "def upsert_\|def insert_\|def update_" <file>` user_id；`grep "lambda m: int"` group(1) | database.md / B-REVIEW-188 / |
| 64 🆕v4.39 experimental | URL，状、同步失败回、 | openSheet 失败时（、栈满）必、 URL 到当，active sheet path，避，useParams 漂移 | `grep "useSheetSync" frontend/src/hooks/` 但、 `useNavigate` 、入或、 `navigate(activeSheet.path)` | state-management.md / F-REVIEW-152（、沉淀、|
| 65 🆕v4.39 experimental | Service Worker 缓存版本同、 | PWA 应用、、时生成版、、希，运、时、、致时、 skipWaiting 、制更、 | `grep "navigator.serviceWorker.getRegistration" frontend/src/` 缺失或无 `SKIP_WAITING` 触、 | frontend-ui.md / F-REVIEW-153（、沉淀、|
| 66 馃啎v4.40 | HTTP 鐘舵、佺爜璇箟鍒嗗眰涓庡啿绐、伩鍏？| | 后、440 专属业务、授权 / 前、：拦、 detail===Unauthorized 校验 / 配置：statusCodeLayering
| 67 🆕v4.41 | CLI 参数、、证与输出解、#205-#206 | cloudflared create 命令参数名变更（--cert --origincert、输出格、、变更、、成解析、 | grep "--origincert" cloudflared tunnel create --help; 正、覆、 Tunnel credentials written to Tunnel .* created with id" | external-service-integration.md / B-REVIEW-190 / F-REVIEW-158 |
| 68 馃啎v4.41 | 澶栭儴鏈嶅、鍓嶇疆渚濊禆妫、#207 | DNS NXDOMAIN 闂涓嶆槸闅ч亾 bug锛屾槸鍩熷悕鏈厤缃叕，DNS 璁板、 | 鍚姩闅ч亾鍓？grep "hostname" config.yaml 骞舵娴？ping hostname | external-service-integration.md / B-REVIEW-191 / F-REVIEW-159 |
| 69 🆕v4.41 | Provider 插件化架、#208 | 新、 Provider 、现基、 + 注册、 TunnelService 、件分、| grep "if.*provider" tunnel_service.py 无从、、件分、| external-service-integration.md / B-REVIEW-192 / F-REVIEW-160 |
| 70 \xf0\x9f\x86\x95v4.42 | 、捷、、独、 API Key 存储规范 | 每个预、、必须有、立凭证存储槽，切换时原子操作（保存当、->加载、->更新 active | grep "api_preset_key_name" secrets.py  per-preset 存储、 | secrets.py ai_preset_key_name() / api_ai.py save_ai_config() / config.yaml credential_storage.per_preset_slots
| 71 \xf0\x9f\x86\x95v4.42 | 配置变更前后、契约规范 | PUT/PATCH 必须回显完整更新状、，前、不、 api_key 发空值、、盖 | PUT 响应、 {ok:true} 无完整配、 / applyPreset 发、 api_key 字、 | api_ai.py save_ai_config 返回 **get_ai_config() / AIConfig/index.tsx applyPreset / config.yaml api.mutation_response_echo
| 70 馃啎v4.41 | 、氱煡闆嗘、 EventBus ″紡 #209 | 闅ч亾鍚姩閫氱煡蹇呴、氳繃 NotifierHub 鍙戦、侊紝绂佹鍦？start() 涓悓、ラ、氱煡 | grep "NotifierHub" src/xianyu_hunter/modules/notifier/ | external-service-integration.md / B-REVIEW-193 / F-REVIEW-161 |
| 71 🆕v4.41 | Provider 前、 UI 状、#210 | 命名隧道向、 login 、时器未清理、、致卸载，setState | grep "setInterval" frontend/src/pages/Maintenance/Tunnel.tsx 但、 useEffect 清、 | external-service-integration.md / B-REVIEW-194 / F-REVIEW-162 | 同一状、、码跨层、、冲突（业，401 vs 认、 401、每层有、、有权，业务异、使，440/422/429 | `grep "CollectionError(401" src/` 命、 、业务代码占用认证层状态码 | meta-rules.md #66 / B-REVIEW-189 / F-REVIEW-154 |
| 67 馃啎v4.41 | 绉、姩绔顖涱梾娴、閲？fallback | 瑙︽懜妫、娴、 鐙珛灞炴€э紙ontouchend + maxTouchPoints锛、紝，Macintosh 鍒嗘、鐢熸、 | `grep "ontouchend.*document" frontend/src/` 浣嗘、 `maxTouchPoints` | meta-rules.md #67 / F-REVIEW-155 |
| 68 🆕v4.41 | 响应、、断点统、 | Hook 阈、、差、必须显、、声明，CSS @media UI Hook 对齐，、值配、 | `grep "MOBILE_VIEWPORT_MAX" frontend/src/` `grep "767" frontend/src/` 值不、| meta-rules.md #68 / F-REVIEW-156 |
| 69 馃啎v4.41 | 璁惧、浠跨湡妯″紡楠岃瘉娓、 | 浠跨湡涓夎绱狅紙UA/maxTouchPoints/innerWidth锛、獙、+ JS 灞炴、цfallback 楠岃、 + 妗岄潰绔槻璇垽蹇、 | 娴、鎶ュ憡鏃？maxTouchPoints 、鏌ユ垨鏃犳闈㈢、闃茶鍒？| meta-rules.md #69 / F-REVIEW-157 |
| 80 🆕v4.48 | async 阻、、调用超时保、 | 、有可能永久挂起的 async API  asyncio.wait_for 包裹，超时、、按成本分类、 config 读取 | `grep "await.*\\.(cookies\\|storage_state\\|snapshot)\\("`  `wait_for` | browser-automation.md / B-REVIEW-226 |
| 81 🆕v4.48 | 子进程心跳与阶、、超时协、 | 每阶段独、 status + 、立阈值，阶、、内阻、、调用超时之、 < 阈、*(1-margin) | `grep "subprocess.Popen"` + `grep "status_file"` 同文、 | concurrency.md / B-REVIEW-227 |
| 82 🆕v4.48 experimental | 跨代码块、致、 | 同一 API 2 处调用时保护、施必须一致，以更严格为准 | grep 同一 API 名出、 2  | browser-automation.md / B-REVIEW-228 |
| 83 🆕v4.49.0 experimental | UI 操作项分级保留与多、、图、致、 | 操作按钮 > 阈、、时按、、率分级（文、/图标/Dropdown）；表格视图与卡片、、图操作集合必须完全、致；Table 必须显式 `scroll` 兜底 | `grep "<Button" <page>.tsx` 计数  6 且无 `<Dropdown`  违、 | frontend-ui.md step 236/237/238 / F-REVIEW-197 / F-REVIEW-198 |
| 84 🆕v4.55 | COOKIE-TOKEN-STATE-SEPARATION 身份 Cookie 与签名 token 分离 | 身份 Cookie 与签名 token 分离管理，token 重置独立于 Cookie 补注入 | `grep "_last_m5tk_refresh"` 检查重置逻辑在补注入分支外部 | browser-automation.md / B-REVIEW-246 |
| 85 🆕v4.55 | 关键路径可观测性与状态同步三要素 | 多步骤进度编号日志 + 超时异常用户友好语义 + 组件复用状态重置 + 字段覆盖集合选择标准 | `grep "asyncio.wait_for"` 检查 except TimeoutError 专门分支 | error-handling.md / B-REVIEW-249 |
| 86 🆕v4.55 | SCHEDULER-STATE-MACHINE-RECOVERY 调度器状态机恢复 | pause/resume 事件配对，暂停是循环回顶部阻塞非退出，should_pause 返回 False | `grep "return True" scheduler.py` 在 should_pause 分支内 | scheduler.md / B-REVIEW-245 |
| 87 🆕v4.55 | CONFIG-FIELD-FIVE-LAYER-COVERAGE 配置字段五层链路覆盖 | 配置字段五层链路（DB/get_config/update_config/types.ts/Config.tsx），空值删除非写空字符串 | get_config 返回字段数 < DB schema 字段数 | config-driven.md / B-REVIEW-247 / F-REVIEW-200 |
| 88 🆕v4.55 | CROSS-LAYER-CONTRACT-SYNC 跨层数据契约同步 | 跨层数据契约同步五步流程，空值语义区分，React 组件复用状态重置 | `grep "_ALWAYS_OVERWRITE"` 检查可能返回空的字段 | frontend-ui.md / B-REVIEW-248 |
| 89 🆕v4.56 | LOGIN-SIDE-EFFECT-AUTOMATION 登录后副作用自动化 | 登录成功路径必须 fire-and-forget 调度副作用（会话续期/状态同步），失败安全不阻塞主流程 | `grep "login.*success\|login.*ok" web/routes/` 检查是否调用 trigger_session_start() | concurrency.md / B-REVIEW-250 / F-REVIEW-205 |
| 90 🆕v4.57 | FALLBACK-PRESERVE-KEY 回退构造保留关联键 | 从部分数据回退构造实体时必须同时注入下游依赖的关联键 | `grep "payload.get\|fallback" src/` 检查是否遗漏 task_id | error-handling.md / B-REVIEW-251 / F-REVIEW-206 |
| 91 🆕v4.57 | TIME-WINDOW-FULL-FALLBACK 时间窗口全量回退 | 时间窗口查询无数据时必须回退到全量查询 | `grep "range_days" src/` 检查是否有回退逻辑 | database.md / B-REVIEW-252 |
| 92 🆕v4.57 | POWERSHELL-EXPLICIT-SUFFIX PowerShell 外部命令显式后缀 | PowerShell 中调用 curl/wget 必须用 .exe 后缀 | `grep "^curl " scripts/` 找到裸 curl | general-engineering.md / B-REVIEW-253 |
| 101 🆕v4.60 | MULTI-WRITE-PATH-STATE-CONSISTENCY 多写入路径状态一致性 | 验证函数依赖中间层状态时，必须检查所有写入路径是否初始化了该状态，或改为直接验证实际数据+自动同步 | `grep "_layer_states\|\.valid\|\.active" src/` 找验证函数引用的中间层状态，再 `grep` 所有写入入口检查是否调用初始化 | state-management.md / B-REVIEW-267 / F-REVIEW-214 |
| 102 🆕v4.60 | UI-PREFERENCE-PERSISTENCE-UNIFIED UI偏好统一持久化 | 用户可配置的UI偏好（pageSize/viewMode/filter/开关）必须使用 usePersistentState 而非 useState | `grep "useState" frontend/src/pages/` 检查变量名是否是用户偏好（pageSize/viewMode/filter/Enabled/Mode），是则改用 usePersistentState | frontend-ui.md / F-REVIEW-215 / F-REVIEW-216 |
| 110 🆕v4.67 experimental | TYPE-ANNOTATION-CONTRACT-ALIGNMENT 类型注解契约对齐 | 后端函数返回类型注解必须与 Pydantic ResponseModel 和前端 types.ts 三方一致；无 ResponseModel 时以前端 types.ts 为反向校验源 | `grep "def.*->.*list\[" src/` 对照前端 types.ts；单元测试仅断言长度未断言结构 | type-annotation-contract.md / B-REVIEW-330 / F-REVIEW-244 |

### 瑙勮寖娌夋穩 SOP锛坢eta-rule #36 、藉湴锛、、焼?v4.33.0

> 鏂扮珛缂、爜瑙、寖锛，eta-rule / step / B-REVIEW / F-REVIEW锛、繀椤、伒，5 姝ユ矇娣、娴佺▼锛岄伩鍏嶅崟涓、 bug 绔、鑼、鑷磋鑼冭、鑳€銆傝缁嗚鍒欒、 [meta-rules.md #36](references/meta-rules.md)

**5 步沉、流、**

1. **相、 bug 、集**： `docs/standards/编码、、复盘.md` 记录每、 bug 的根、、文件、、模块、、同、根因在不同文、、块出、 `config.yaml#meta_rules_governance.sedimentation_threshold`（3、才可、、范，时间、 6 
2. **门、校验**：立、、前必，grep 历史教、、相、 bug 计数、。未达标但希望、沉淀的，`experimental` 标、 + 1 季度观察、
3. **、豁免**：安全漏、/ 数据丢失 / bug 、即立规范，无、  次，但必须标注豁免、
4. **规范编写**：、标后写入 meta-rules.md（、情）+ SKILL.md（、查、+ 对、 step 文、 + B/F-REVIEW 、查、 + config.yaml 配置节点
5. **防回、*： unit test 覆盖了、、条、 + 更、 version-history.md

**关、判、**
- 单、 bug 、范（experimental 标、）→ 规范膨胀风、
- experimental 标、1 季度、、级为正、 、废弃候、
- 、豁免、、范但、、注豁免、、无法、

### 瑙勮寖閫、鍖栨竻鐞?SOP锛坢eta-rule #37 、藉湴锛、、焼?v4.33.0

> 每、度统、 step / B-REVIEW / F-REVIEW 利用率，利用、< 3 、季度则标、待合、、待废、，避免、范、圾堆、、细、则、 [meta-rules.md #37](references/meta-rules.md)

**瀛ｅ害娓、悊娴佺▼**

1. **利用率统、*：每、、度、 step / B-REVIEW / F-REVIEW 在、查报告中、、数，输出利用率排行、
2. **、化标、*：利用率 < `config.yaml#meta_rules_governance.degradation_threshold`（3 、季度）则标、"待合、、待废、
3. **合并优先**：相，step 优先合并（ 3 datetime  step 合并，1 ，废、是、后手、
4. **观察、*：标、待废、 1 季度观察期（`observation_period_quarters`，1，无命、、废、
5. **废弃归、**：废、 step / B-REVIEW  `version-history.md` Deprecated 章、，保留历史、

**、豁、*oken 比、 / 加、 / 认证白名单等、、范永不、、化，即使 0 命中也保留、

### 规范适用边、（meta-rule #2 、地、

> 姣忔、缂栫爜瑙、寖蹇呴、鏄庣、璇存、**、傜敤鍦烘、***涓嶉、傜敤鍦烘、**锛岀‘淇濋€氱敤、э紝閬、厤、℃煡鏃惰ㄤ簬涓嶉、傜敤鍦烘櫙銆傝缁嗚鍒欒 [meta-rules.md #2](references/meta-rules.md)

**、傜敤杈圭、澹版槑妯℃澘**锛堟瘡鏉?meta-rule / step / B-REVIEW / F-REVIEW 蹇呴』鍖、惈锛夛細

```
**、用**、具体场景、，"、调、pause/resume、登录会话失、">
**不、、用**、排除场景、，"、户、 pause、一次、、任务、、纯函数重试">
```

**边、声明、查清、*
- [ ] 、用场景具体（"、这、模糊描、
- [ ] 不、、用场景明、（列出排除、
- [ ] 不、、用场景有替代方、（xxx 替、"
- [ ] 边、config 参数、、齐（" item 的、批量操作不、、用"对、 `batch_size` 参数、

**、歌涓嶉、傜敤鍦烘、**锛堥、氱敤鎺掗櫎椤癸級
- 绾牱、bug锛堥鑹？闂、窛/瀛、彿锛？
- 鍗曡、 typo锛堥敊鍒瓧/鏍囩偣锛？
- 绾、寤洪敊璇紙渚濊禆缂哄け/鐗堟湰鍐、獊锛？
-  hot path（持、/校验、、不可接受、
- 瀹為獙鎬？feature 璇曢敊锛堟晠鎰忛绻佸け璐ワ
- ㄦ埛涓、、姩鎿嶄綔锛堥潪、傚父瑙﹀彂锛?

## 鎵ц姝ラ

### 绗竴闃舵锛氶渶姹傚垎鏋愪笌瑙、寖纭顔款吇

1. **闇€姹傜悊瑙?*
   - 浠旂粏闃呰ㄦ埛闇€姹傦紝鏄庣、鍔熻兘鐩爣涓庨獙、舵爣
   - 识别涉及的层（domain / infra / modules / web / frontend
   - 璇勪及鏄惁闇€瑕佹暟鎹簱杩佺Щ銆丄PI 璺敱鏂板銆佸墠绔粍浠舵敼閫？

2. **规范、查、、制、*
   - 必须先、[project-rules.md](references/project-rules.md) 了解项目、
   - 后、、发：必、、查是否触及、证白名单、安全、、束、、并发模、
   - 前、、发：必、SonarQube 规、（S2004/S3358/S6757/S7784/S6848/S1128/S4325/S3776
   - 数据库开发：必、、查索、、策略与迁移幂等、

3. **鍙傝、冨垎、*
   - 同、功能、、现、 `src/xianyu_hunter/` `frontend/src/` 、索相似模、
   - 璁捐鏂囨、锛、煡闃？`docs/01-浠〃鐩？` `docs/08-绉、姩、` 瀵瑰簲妯″潡鐨勮缁嗚
   - 鍘嗗彶鏁欒锛氬、[architecture-patterns.md](references/architecture-patterns.md) 涓殑韪╁潙璁板

4. **、发指、、考、、制、*
   - **前、*: 必须参、[前、、发指、(assets/guides/frontend-guide.md)
   - **后、*: 必须参、[后、、发指、(assets/guides/backend-guide.md)
   - **数据库开、*: 必须参、[数据库开发指、(assets/guides/database-guide.md)
   - **智能、、服、*: 必须参、[智能、、服、发指、(assets/guides/chatbot-guide.md)
   - **🆕 SonarQube 规、预、**: 编码时主动、[SonarQube 规、、查](assets/guides/sonarqube-rules-guide.md) 预防、（、杂、 15、嵌、4、不必、 `async`、可访问、等、
   - **项目、**: 必须遵守 [项目、](references/project-rules.md)
   - **架、、式**: 、并发、事件、、调度、、录等场景，必、[架、、式、识库](references/architecture-patterns.md)
   - **FAQ**: 、到、先查、[faq.md](references/faq.md)

### 绗簩闃舵锛氬紑鍙戝疄

1. **后、*
   - **指南参、*: 先、[后、、发指、- 代码模板](assets/guides/backend-guide.md#二、、模、 章、
   - ***: 新、 `src/xianyu_hunter/web/routes/api_.py`，使、`APIRouter(prefix="/api/", tags=[""])`
   - **业务模块**: 新、/ `src/xianyu_hunter/modules/.py` `modules//` 子、
   - **仓储、*: 新、 `src/xianyu_hunter/infra/repo_.py` Mixin，并、`infra/repository.py` 
   - **领域模、**: 新、/ `src/xianyu_hunter/domain/.py`，dataclass + Enum， IO 依、
   - **依赖注入**: `container.py` 、配新依赖（Composition Root
   - **、钩子**: 、后台调、`web/startup.py` 注、 startup/shutdown

2. **前、*
   - **指南参、*: 先、[前、、发指、- 代码模板](assets/guides/frontend-guide.md#二、、模、 章、
   - **API 、块**: 新、 `frontend/src/api/.ts`，`Api`， `api/index.ts` re-export
   - ****: `api/types.ts` 、分组追、、类、
   - **页、**: 新、 `frontend/src/pages//index.tsx`， `App.tsx` 注册、（`lazyRetry`
   - **菜、**: `MainLayout.tsx` `menuItems` 注册，在 `sheetRegistry.tsx` 维、 path component 映、
   - **Hook**: 复用现有 `hooks/use*.ts`，、要时新、 `use<Feature>.ts`
   - **Store**: 、跨页状、，新、 `stores/<feature>Store.ts`，`use<Feature>Store`

3. **数据库开、*
   - **指南参、*: 必须参、[数据库开发指、(assets/guides/database-guide.md)
   - **新、*: `infra/db_models.py` `*Row(Base)` ，、循 SQLAlchemy 2.0 `Mapped[T] + mapped_column` 风、
   - **新、**: `init_db()` `_migrate_add_column` 调用（幂、、则跳过）
   - **新、索引**: `init_db()` `_migrate_create_index` 调用（幂、
   - **、列、*: SQLite 不、ALTER COLUMN，使、`_migrate_make_column_nullable` 表重、、模、
   - **仓储方法**: `infra/repo_.py` CRUD，JSON `RepositoryBase._row_to_dict` 白名单中注、

4. **智能、、服、*
   - **指南参、*: 必须参、[智能、、服、发指、(assets/guides/chatbot-guide.md)
   - **新工、*: `modules/chatbot/tools/` 新、、具类，继、 `BaseTool`， `tool_registry.py` 注、
   - **KB 数据、*:  `KBManager._scan_and_chunk` 的扫描、则（白名单：`.md/.py/.jsonl/.txt`
   - **降级、*: `ChatbotOrchestrator._handle_*` 、加、、级分、、发、 `CHATBOT_DEGRADED` 


---

### 、缂栫爜瑙、寖锛堟寜闇€鍔犺浇锛?

> **、原包，178 step 编码、（ 30 万字符），已按主题归、 `assets/guides/coding-rules/` 12 、件、*
> 
> **加载、**
> 1. **AI 、主、、加、**：例如、`frontend-ui.md`，数、、加载 `database.md`
> 2. **元、范优、*：所有任、、加、 [meta-rules.md](references/meta-rules.md)1 条、则，8K 
> 3. **step 编号查、**：、过 [编码、、索引](assets/guides/coding-rules/_step-index.md) 定位特定 step
> 4. **版本、**：、过 [version-history.md](references/version-history.md) 了解各、、历史背、

**、查、*

| 、类、 | 应加载的规范文、 |
|---|---|
| 认、/加、/外、 API | security.md + meta-rules.md |
| /并、/后台任、 | concurrency.md + meta-rules.md |
| 状、、缓、 | state-management.md + meta-rules.md |
| 错、/重、 | error-handling.md + meta-rules.md |
| DB schema 变、 | database.md + meta-rules.md |
| 配置、| config-driven.md + meta-rules.md |
| React 组、/UI | frontend-ui.md + meta-rules.md |
| 、编、 | testing.md + meta-rules.md |
| 调度、定时任、 | scheduler.md + meta-rules.md |
| LLM 调、 | llm-ai.md + meta-rules.md |
| 浏、器自动、 | browser-automation.md + meta-rules.md |
| 、用编、 | general-engineering.md + meta-rules.md |

---

### 绗笁闃舵锛氶獙璇佷笌浜や

1. ***
   - 鍚庣、锛歚mypy` 鏈惎鐢紝渚濊、 Pydantic 杩愯鏃舵牎
   - 前、：`cd frontend; npx tsc -b`（、建前、、制、、查、

2. **、执、**
   - 后、：`pytest tests/`（asyncio_mode=auto 、识别 async 
   - 前、：`cd frontend; npx vitest run`

3. **代码、**
   - 前、代码、、查：调、`xianyu-frontend-code-review` Skill
   - 后、代码、、查：调、`xianyu-backend-code-review` Skill
   - SonarQube ：调、`xianyu-sonarqube-mcp` Skill

4. **、排查**
   - 、到、先查、[faq.md](references/faq.md)
   - 、架、疑问查、 [architecture-patterns.md](references/architecture-patterns.md)
   - 、反、//Cookie 链路，参、`xianyu-automation-startserver` Skill `docs/04-、统维、/反爬登录管、-详细设、.md`

### 绗洓闃舵锛、it 鎿嶄綔瑙、寖涓？Bug 淇

1. **合并前、查、、制、*
   - `.git/index.lock` （失，git 操作、、留下锁文件、致后、、作全失败、
   - 、查工作区、、干净（ modified 文件时先 stash
   - 、查当前分、、否、`git branch --show-current`
   - 、查是否有产物文件，git track（`.scannerwork/`、`__pycache__/` 

2. **产物文件、、制、*
   - `.scannerwork/`、`node_modules/`、`dist/`、`__pycache__/` 、物不应、 git track
   - 发现、 track 时、 `git rm -r --cached <dir>` 清理（不删除、、作区文、
   -  `.gitignore` 已包、应路、
   - 清理后提交、 chore commit，、进、合并

3. **stash 操作注意、**
   - stash 前确认无大目录（`.scannerwork/` modified，避免权限问题、stash 失、
   - stash 失败后必须、`.git/index.lock` 
   - PowerShell `stash@{0}` 必须加引号：`git stash pop 'stash@{0}'`（避免哈、、解、、错、

4. **.git 鐩綍鎿嶄綔**
   - PowerShell `cmd /c` 鍙兘琚畨鍏ㄧ瓥鐣ラ樆姝㈡搷浣？`.git` 鐩
   - 鏇夸、鏂、锛氱、 Python `os.remove()` 鍒犻、 `.git` 涓、枃浠讹紝鎴栫、 git 鍛戒护鏈韩鎿嶄
   - 、轰緥锛歚python -c "import os; os.remove('.git/index.lock')"`

5. **鍐茬獊瑙ｅ喅鍘熷、**
   - 保、更新版本（ main `await` 、版本优于 feat 的同、、版、
   - 鍚屼竴鍔熻兘涓ゅ垎鏀兘鏈、慨、规、锛岄€夋、璇箟鏇村、鏁、殑鐗堟
   - cherry-pick 鍚庣殑鍚堝苟鍐茬獊锛歮ain 宸叉、 cherry-pick 鐨勬敼鍔紝feat 鏈、師、敼鍔紝淇濈、 main 鐗堟

6. **Bug 、流程【强制、*
   - **根因、**：、数据、、定位、小修、
   - **、小修、*：只、、必、、不、、便重构（遵循、、原、
   - **验证、**：`tsc --noEmit` 验证类、 、运、专、 、必、时、、动验、
   - **状、、致、*：修复状、bug 、查操作是否同、、更新、、有相关状态字、

7. **、兼、*
   - Node v24 + vitest 4.x 存、 worker ，测试命令必、 `--no-isolate`
   - antd 组件（Drawer/Grid/Skeleton jsdom `window.matchMedia` mock
   - vitest  RUN 阶、时，`tsc --noEmit` 作为类、、证、
   - 、命令示例：`node node_modules/vitest/vitest.mjs run --no-isolate <test-file>`


## 鐩、、叧 Skills 鍗忎、

| Skill | 协作场景 |
|---|---|
| `xianyu-automation-startserver` | 、服、、、建、、状、|
| `xianyu-backend-code-review` | 后、代码、ython/FastAPI、|
| `xianyu-frontend-code-review` | 前、代码、eact/TypeScript、|
| `xianyu-sonarqube-mcp` | SonarQube 代码质量、、与问题修、|
| `xianyu-logs-review` | 运、时日、 WARNING/ERROR 排、 |

## 闃舵浜ゆ帴澹版

- 当前阶、：v4.45.0 多用、 Cookie 隔、、范  已完成`n- 新、 meta-rules #72-#78、7 条）：、用、 Cookie 隔、、传、、注入验证、M5TK 刷新隔、、层状、、同步缓存清除、、实时搜、 Cookie 健康、查、、测、 Cookie 过滤、文件路径安全构造`n- 新、 B-REVIEW-209~217、9 条）：后、 Cookie 隔、、查维度`n- 新、 F-REVIEW-178~181、4 条）：前、 Cookie 状、、同步、、查维度`n- 新、 step 216~222、7 条）：、用、 Cookie 隔、、编码、、范`n- 新、 coding-rules/multi-user-cookie-isolation.md、7 条强制、、范（R1-R7）`n- 、复问题：实时搜索 FAIL_SYS_ILLEGAL_ACCESS - user_id  _ensure_live_search_cookies 调用链中丢失
- 新、 step 214（模型名称大小写敏感规范）：、有、、模型名称必须与官网逐字符一、
- 新、 step 215（配、输入框、、持久化与返显、、范）：、有输入、、变更即持久化，PUT 响应回显完整状、
-  DeepSeek 预、、默认模型：deepseek-chat  deepseek-v4-flash（全小写、
- 、正百、 ERNIE 模型名称大小写：ernie-speed-128k  ERNIE-Speed-8K
- 新、 meta-rules #74（后、逻辑变更、前、文档同、） #75（价格区间评分阈值可配置化）
- 新、 B-REVIEW-218~221（前、文档同、/价格评分、配置/向后兼、/冲突解决优先级）
- 新、 F-REVIEW-182~187（、则、见、/示例准确、/配置来源/构建产物管理/构建验证/PWA缓存、
- 新、 coding-standards 、十章至、十四章（合并冲突/构建管理/选择性暂、/PowerShell编码/价格区间、视化、
- 、正百、 ERNIE 模型名称大小写：ernie-speed-128k  ERNIE-Speed-8K
- 前、审查新、 F-REVIEW-173~177、5 项）
- 后、审查新、 B-REVIEW-203~208、6 项）
- 新建 coding-rules/ai-service-config.md 归档 2 步、、范
- 更新 _step-index.json  _step-index.md 索引
下一階、：v4.44.0 规划、（meta-rules #70-#71）✅ 已完、
- 当前阶、：v4.49.0 UI 操作项分级保留与多、、图、致、  已完、
  - 新、 meta-rule #83（UI-ACTION-TIER-RETAIN-AND-MULTI-VIEW-CONSISTENCY experimental
  - 新、 step 236/237/238 三条编码规范（操作项分级保留 / 多、、图、致、 / 、向溢出诊、 scroll fallback
  -  tech-stack.json 新、 `hardConstraints.uiLayout` 配置段（actionButtonVisibleThreshold/lowFrequencyThresholdPerMonth/collapseContainerStrategy/scrollFallback/multiViewSyncRequired 等参数）
  - 、有阈值与策略均、、过 config 管理，、代码、编码
  - 复盘来源：TaskList.tsx 操作、 6 、文字按钮溢出页面样式 Bug、2026-07-18 、复）
- 下一阶、：v4.50.0 规划、
- 下一阶、、智能体：bemp-personalized-developer  xianyu 代码审查相关智能、
- 下一阶、、技能：xianyu-hunter-dev / xianyu-frontend-code-review / xianyu-backend-code-review
- 交接上下文：、基于 TaskList.tsx 操作列溢、 Bug 、复后四维度、、盘（Sequential Thinking 5 步法），新、 meta-rule #83  step 236/237/238 三条编码规范，沉、"UI 水平空间溢出诊断流程 / 操作项分级保留范、 / 多、、图模式、致、、查流、"三条、抽象流程。所有阈值参数、、过 `config/tech-stack.json#hardConstraints.uiLayout` 集中管理，无、编码。同步在前、审查新、 F-REVIEW-197/198、后、审查新、 B-REVIEW-237、auto-testing 新、、模、 F（UI 布局溢出回归测试）
- 、阶、智能体：bemp-personalized-developer xianyu 代码、、查相关智能、
- 、阶、、能：xianyu-hunter-dev / xianyu-frontend-code-review / xianyu-backend-code-review
- 交接上下文：、基于"AI 服务、捷、 API Key 不跟随变、"Bug 、复后四维度、、盘，新、 meta-rules #70（快捷、、独、 API Key 存储规范）和 #71（配、变更前后、契约规范），完成预、、凭证独立槽位、、配、变更响应回显、前、 Key 字、、约三大维度沉淀、

- 当前阶段：v4.54.0 配置字段全链路覆盖 + 空值恢复默认语义 ✅ 已完成
  - 新增 meta-rule #86（配置字段全链路覆盖检查）和 #87（空值=恢复默认语义）
  - 新增 step 251（配置字段 5 层覆盖规范）和 step 252（空值=恢复默认设计模式）
  - 复盘来源：智能客服新建会话乱码 Bug（2026-07-11 修复）
  - 根因：DB welcome_message 被写入占位串 '!'，Config.tsx 缺少编辑 UI 导致脏值不可清
  - 修复：补全 5 层链路（DB DELETE + get_config 返回 + update_config 空值短路 + types.ts + Config.tsx TextArea + 恢复默认按钮）
- 下一阶段：v4.55.0 规划
- 下一阶段智能体：bemp-personalized-developer 或 xianyu 代码审查相关智能体
- 下一阶段技能：xianyu-hunter-dev / xianyu-frontend-code-review / xianyu-backend-code-review
- 交接上下文：基于"智能客服新建会话乱码"Bug 修复后四维度复盘（Sequential Thinking 5 步法），新增 meta-rule #86/#87 和 step 251/252，沉淀"DB 脏值诊断流程 / 配置字段全链路覆盖检查 / 空值=恢复默认语义"三条可抽象流程。所有阈值参数通过 config/tech-stack.json#hardConstraints.configFieldCoverage 集中管理，无硬编码。同步在前端审查新增 F-REVIEW-200/201、后端审查新增 B-REVIEW-238/239、auto-testing 新增模式 K（DB 脏值诊断测试）。

## 版本历史

> 版本历史已、移到 [references/version-history.md](references/version-history.md)
> 
> 覆盖范围、4.14.0 v4.29.0，包、
> - 新、 step 编号与、范标、
> - 复盘方法（Sequential Thinking N 步法、
> - 代码、
> - 审查、能同、、落地情、
> - 历史教、

## 复盘与规范沉淀

> 完整复盘报告见 references/retrospective-*.md 系列文件。
> 111 条元规范速查索引见 [references/meta-rules/index.md](references/meta-rules/index.md)，按 10 个类别分组，支持关键词快速定位。

# 闲鱼猎人 (Xianyu Hunter) 、发、、范

> 、文档从实际开发中沉淀的历史问题出发，提炼系统性编码、、范、
> 、有、、范均以"预防同类、题再次发、"为目标，而非事后补救、

## 、成功执行任务的完整步、

### 案例 1：AI 、速、、切、  API Key 跟随模型变化

（保留原文，略）

### 案例 2：评估明细价格区间与分布统、、口径不、

#### 背景
评估明细菜单显示价格区间、 ¥210~800，与任务价格区间、评估列表商品实际价格范围不、致、、根因是 /api/evaluations/distribution 接口忽略、 	ask_id  min_price/max_price 参数，、致统、、卡片、、热力图、分数分布等、有依、 distribution 数据、 UI 组件展示的是全量数据而非当前列表过滤后的数据、

#### 完整解决步、

1. **定位根因（Phase 1**
   - 对比 list_evaluations  evaluations_distribution 两个接口的参数、、名
   - 、认列表接口已、 	ask_id/min_price/max_price/include_out_of_range 参数
   -  distribution 接口缺少这些参数，统计样、集未受过、

2. **、向排查同类问题（Phase 2**
   -  	hresholdSuggestionuto-collect-statseedback/stats 等依赖评估事件的接口
   - 、认它、同样、接受任务/价格过滤参数
   - 、认前、 loadDist() 调用时未传、、当前筛选条、

3. **、小化、复（Phase 3**
   - 后、：、用列表接口已有、 _match_task_id_filter、_filter_price_range、_apply_task_price_fallback 函数，确、 distribution 与列表使用完全相同的过滤逻辑
   - 前、：loadDist()  iltersRef.current 读取当前筛、、条件并传、、给 distribution API
   - 测试：新增回归测试验、 distribution 按任、 ID 和价格范围收敛样、

4. **验证（Phase 4**
   - 运、、新增的 2 、回归测试，确认红、→绿、
   - 运、、全、 53 、相关测试，确认无回归
   - 前、构建通过，无类型错、

---

## 二、、任务执行过程中的不、定、、与失败、

（保留原文不、定、 1-4

### 不确定、 5：统计接口与列表接口的过滤口径一致、
- ****：列表接口和分布接口的样、集不同、，导致统、、卡片显示全量数、
- **失败、**：新增接口时、对照已有接口的参数、、名，遗漏了 	ask_id/min_price/max_price 等过滤参、
- **教、**：凡、基于同一数据源的多个接口，必须保证过滤口径一致；新、、接口时应列、"上游接口有哪些过滤参数，我是否也、"的、查清、

### 不确定、 6：前、状、、与 API 调用的联、
- ****：前、 loadDist() 、立于 load()，未共享筛、、条、
- **失败、**：用户切、任务或调整价格范围后，列表刷新了但分布数、、刷新
- **教、**：共用同、组筛选条件的多个 API 调用，应通过 ref 集中管理参数，避免各调用各自维护状、

---


### 不确定、 7：浏览器锁竞争、、致手动抢单与后台搜索冲、
- ****：手动抢单接口未获取 browser_lock，与后台搜索任务并发执、、同、浏、、器实例
- **失败、**：manual_takeover 接口直接调用 Buyer.start() 而未先获、 browser_lock
- **教、**：所有涉及浏览器操作的代码路径必须、、过全局锁序列化，无论手动触发还、后台、

### 不确定、 8：新建页面、 scheduler 、关闭
- ****：Buyer._do_buy() 创建的页面未注册、 external page， scheduler.close_all_pages() 
- **失败、**：页面生命周期、、理与调度器的清理、、辑之间缺乏协调机制
- **教、**：新建页面必须调、 register_external_page() 注册，结束时调用 unregister_external_page() 并主动关、

---
## 三、、可抽象的固定流程与判断逻辑

（保留原文流、 1-4

### 流程 5：统计接口的"过滤口径、致、"范式


新、、统计接、  列出上游列表接口的过滤参、  逐一、查是否需、  复用同一过滤函数  前、调用时传递当前筛选条、


**判断逻辑**
`
对于每个统、/分布类接口：
  1. 它的数据源是否与列表接口相同、
  2. 如果、，上游列表接口有、些过滤参数？
  3. 我的接口、否也接受了这些参数？
  4. 我是用同、套过滤、、辑，还、各自实现了一套？
  5. 前、调用我时，是否传递了当前筛、、条件？
  任一答、、为、  、要修、
`

### 流程 6：前、 API 调用、"单一来源"范式


筛、、条、  filtersRef.current 集中持有  load()  loadDist() 都从此、、取  保证参数、


---


### 流程 7：浏览器操作的锁+注册范式

获取 browser_lock -> 同、 Cookie -> 执、、浏览器操作（Buyer.start / scheduler.run -> 释放 browser_lock

对于新建页面、
Buyer._do_buy() 创建页面 -> register_external_page() -> 执、、购、 -> unregister_external_page() -> 关闭页面

**判断逻辑**
对于每个涉及浏、、器操作的代码路径：
  1. 、否、、过 browser_lock 序列化？
  2. Cookie 同、、是否在锁内执、？
  3. 新建页面、否注册为 external page
  4. 页面结束时是否主动注、并关、
  任一答、、为、 -> 、要修、

---
## 四、、用场景与不适用场景

### 适用场景
- 任何涉及"多配、切换"的功、
- 任何涉及"敏感信息存储"的场、
- 任何涉及"前后、状、、同、"的场、
- 任何涉及"功能降级"的场、
- **任何涉及"统、/分布类接、"的开、**（新增时必须对照上游列表接口的过滤参数）
- **- **任何涉及"多个 API 调用共用同一筛、、条、"的场、**（应通过 ref 集中管理参数、
- **任何涉及"浏、、器操作"的场、**（必须、、过 browser_lock 序列化，新建页面、注册、 external page**（应通过 ref 集中管理参数、

### 不、、用场景
- 不涉及状态变更的、读配、展示
- 不涉及敏感信、的普通配、
- 、次、、操、
- 、立数、源的统、、接口（如系统健康度、CPU 使用率等，与业务列表无关、

---

## 五、、已、认的编码规范和技、标准

### 规范 1：配、切换必须"先保存后更新状、"
（保留原文）

### 规范 2：敏感信、必须分槽存储
（保留原文）

### 规范 3：脱敏、、回传必须跳过更、
（保留原文）

### 规范 4：配、切换必须处理迁移
（保留原文）

### 规范 5：配、回显必须包含派生字、
（保留原文）

### 规范 6：功能开关必须实现降级路、
（保留原文）

### 规范 7：前后、配置模型必须、
（保留原文）

### 规范 8：所有可配置参数必须通过配置文件管理
（保留原文）

### 规范 9：、则文件必须与配、文件分、
（保留原文）

### 规范 10：代码、、查必须分层、
（保留原文）

### 规范 11：统计接口必须与列表接口过滤口径、
- **规则**：基于同、数据源的统、/分布类接口，必须接受与列表接口相同的过滤参数（ 	ask_id、min_price、max_price、include_out_of_range 等），并使用相同的过滤、、辑
- **原因**：避免统计卡片、、热力图、分布图、 UI 组件展示与列表不、致的全量数据
- **实现**：新增统计接口时，、照上游列表接口的参数、、名逐项、查；优先复用已有过滤函数而非重新实现

### 规范 12：前、 API 调用必须共享筛、、条、
- **规则**：当多个 API 调用共用同一组筛选条件时，必须、、过单一来源（ useRef）集、管理，各调用从、 ref 读取参数
- **原因**：避免各调用各自维护状、、致参数不一、
- **实现**：使、 iltersRef.current 持有、有筛选条件，load()  loadDist() 都从此、、取

### 规范 13：新增接口必须、、照已有接口、查参、
- **规则**：新、 API 、点时，必须列出上游同类接口的、有参数，逐一、查是否需、
- **原因**：防止遗漏过滤参数、、致数据口径不一、
- **实现**：在 PR 描述或代码注释中列出"上游接口参数清单及我的、、理方式"


### 案例 3：手动抢单浏览器锁竞争与页面、关闭

#### 背景
手动抢单时后台搜、任务同时运、，导致浏、、器锁竞争和页面、关闭。用户在前、点击"手动接、"触发抢单操作，同时后台定时搜、任务也在运、，两、、共、同一、浏、、器实例，引发以下问题：

1. manual_takeover 接口、获取 rowser_lock，与后台搜索并发执、
2. Buyer._do_buy() 创建的页面未注册、 external page， scheduler.close_all_pages() 
3. Cookie 同、、在锁、、执行，、能、、致跨、、求、 Cookie 不一、

#### 完整解决步、

1. **定位根因（Phase 1**
   - 对比 manual_takeover 与后台搜、任务的锁获取逻辑
   -  manual_takeover 接口直接调用 Buyer.start() 而未获取 rowser_lock
   -  Buyer._do_buy() 创建页面后未调用 
egister_external_page()
   -  scheduler.close_all_pages() 会关、、注册的页、

2. **、小化、复（Phase 2**
   - 后、 manual_takeover 接口、 priority="high" 获取 rowser_lock
   - Buyer 创建页面后调、 
egister_external_page()，结束时调用 unregister_external_page() 并关、
   - Cookie 同、、移入锁内执、

3. **验证（Phase 3**
   - 手动抢单与后台搜索并发执行，、认不再出现锁竞争
   -  Buyer 创建的页、不会、 scheduler 
   -  Cookie 在锁内同步，跨、、求、致、、得到保、

---
### 规范 14：浏览器操作必须通过全局锁序列化
- **规则**：所有涉及浏览器操作的代码路径（包括手动触发和后台自动任务）必须通过 browser_lock 序列化执、
- **原因**：浏览器实例、共享资源，并发操作会导致锁竞争、、页面、关闭、Cookie 不一致等、
- **实现**：接口层获取 browser_lock（手动操作使、 priority="high"），Cookie 同、、移入锁内执、

### 规范 15：新建页面必须注册为 external page
- **规则**：Buyer 等模块创建的新页面必须调、 register_external_page() 注册，结束时调用 unregister_external_page() 并主动关、
- **原因**：scheduler.close_all_pages() 会关、、注册的页、，、致手动抢单创建的页面、
- **实现**：在 Buyer._do_buy() 创建页面后立即注册， finally 块中注销并关、

### 规范 16：浏览器操作必须、 URL 诊断日志
- **规则**：所有浏览器操作的关、节点必须记录当前 URL 的诊、日志
- **原因**：浏览器状、、异常时，URL 、直接的诊、依据，可以帮助快速定位页面跳、、重定向、登录、、失效等、
- **实现**：在获取锁后、执行操作前、操作完成后记录 page.url

---
## 、新增、、范的完整、、盘

### 复盘：手动抢单浏览器锁竞争与页面、关闭

**时间、**
1. 用户在前、点击手动接、、触发抢、
2. 后台定时搜索任务同时运、
3. 两、、共、同一浏、、器实例但未序列化执、
4. Buyer创建页面、被scheduler识别为、、部页面
5. scheduler.close_all_pages，关了Buyer创建的页、
6. Cookie同、、在锁、、执行，跨、、求、致、、无法保、

**根因分析**
- manual_takeover接口缺少browser_lock获取逻辑
- Buyer页面生命周期管理缺失
- Cookie同、、不在锁内，存在竞、、窗、

**、复措、**
- manual_takeover、priority=high获取browser_lock
- Buyer创建页面后register_external_page，结束时unregister_external_page并关、
- Cookie同、、移入锁内执、

**Ԥ**
- 规范14：所有浏览器操作必须通过browser_lock序列、
- 规范15：新建页面必须注册为external page
- 规范16：浏览器操作必须有URL诊断日志

**验证方法**
- 手动抢单与后台搜索并发执行，、认无锁竞、
- Buyer创建的页、不、scheduler
- Cookie在锁内同步，跨、、求、致、、常---

---
## 四、、新增、、范：Cookie 与登录、、理

### 规范 17：身、 Cookie 必须比较值、、非仅、查存在、

**、题现、**：登录成功后，worker 浏、、器仍持有旧同名 Cookie（ unb=old_uid），导致后续搜索/详情/采集使用旧登录、，表现、"官方采集超时""实时搜索不可、"

**根因**：登录、、查只验证 cookie 名称、否存、（cookie2, sgcookie, unb），不比较、、是否一致、、同名但值陈旧时，系统、判为"已登、"

**、复措、**
- 、有登录、、查必须执行三要素验证：缺失（missing）、过期（expired）、陈旧（stale
-  CookieStore JSON 读取、 Cookie 值，与浏览器内存、 Cookie 值、、一对比
- 发现陈旧 Cookie 时， JSON 注入/替换到浏览器内存

**判断逻辑**
`
对于每个关键 Cookie（cookie2, sgcookie, unb）：
  1. 浏、、器、、否存、
  2. 如果存在，expires 、否已过期、
  3. 如果、过期，、是否与 CookieStore JSON 、的最新、、一致？
  任一答、、为、  、要修、
`

**适用范围**：实时搜、（api_task_links.py）、官方采集（api_evaluations.py）、健康、查（api_anticrawl.py）、情页采集（_detail.py）、卖家主页采集（_detail.py）、手动抢单（api_orders.py）、商品、、情刷新（api_items.py）

---

### 规范 18：CookieStore 读取前必、 invalidate_cache()

**、题现、**：浏览器登录子进程写、 cookies.json 后，主进、 30  TTL 缓存仍是旧数、（空数据或旧 cookie），导致层状态无法及时更新、、健康、查、判失效、

**根因**：子进程、 Python 进程，只写文件不更新主进程缓存、、主进程读取 JSON 前未清缓存，读到 30 秒前的旧数据、

**、复措、**
- 、有从 CookieStore JSON 读取的路径，在调、 _read_json() 前先调用 store.invalidate_cache()
- 适用入口：健康、查、cookie_checker、session start、cookie provider/cookies/layers/cookies/update/me、auth_query、worker 搜索前同、

**判断逻辑**
`
读取 CookieStore JSON 前：
  1. 、否调用了 invalidate_cache()
  2. 如果、外部进程写入（子进程、定时任务），是否清缓存、
  任一答、、为、  、要修、
`

---

### 规范 19：Cookie 写入后必须同、 worker 浏、、器上下、

**、题现、**：登、/导入/更新 Cookie 后，JSON 和层状、、已更新，但运、、中、 worker 浏、、器内存仍持有旧 Cookie。后、搜索/详情/采集使用旧登录、，导致 API 不可用、

**根因**：CookieStore JSON 和浏览器内存、两个、立的数据源、、写、 JSON 后必须主动推送到浏、、器上下文、

**、复措、**
-  Cookie 写入成功后，必须调用 inject_cookie_store_to_worker_browser() 将最、 Cookie 推、、到 worker 浏、、器
-  Cookie 变更时，必须强制刷新 _m_h5_tk token
- 写入失败时（如浏览器、初、、化），记录日志但不阻、、主流程

**适用范围**：统、登录（unified_login.py）、浏览器登录（browser_login.py）Cookie 注入（cookie_inject.py）、浏览器导入（browser_import.py）CDP 导入（browser_import_cdp.py）Cookie 更新（api_anticrawl.py）、手动抢单（api_orders.py）、商品刷新（api_items.py）、后、 worker 搜索前、

---

### 规范 20：BrowserManager.add_cookies() 必须验证、 Cookie 而非仅关、 Cookie

**、题现、**：只更新 _m_h5_tk 时，add_cookies() 返回 False（因为找不到 cookie2/sgcookie/unb），导致注入失败、

**根因**dd_cookies() 的验证、、辑、 cookie2/sgcookie/unb 、否存、，不、查本次注入的、 Cookie 、否在浏、、器、、见、

**、复措、**
- add_cookies() 成功判定改为：本次注入的、 Cookie 能在浏、、器、查到
- 日志同时记录、 Cookie 验证结果和关、 Cookie 验证结果
- 避免因只更新部分 Cookie 导致注入、、判为失败

---

### 规范 21：Cookie 注入必须通过 BrowserManager 封、

**、题现、**：cookie_inject.py 直接调用 ctx.add_cookies() 绕过 BrowserManager.add_cookies() 封、，导致注入后无法验、 Cookie 、否成功写入、

**根因**：直接操、 Playwright context 跳过、 BrowserManager 的统、校验和日志、、录、

**、复措、**
-  Cookie 注入必须通过 rowser.add_cookies() 封、、方、
- 禁、、直接调、 context.add_cookies()  page.context.add_cookies()

---

### 规范 22：后台任务搜索前必须同、 Cookie  worker

**、题现、**：CookieSyncScheduler 或、、线导入写入 JSON 后，后台定时任务仍使用旧的浏览器内存 Cookie，、致采集失败、

**根因**：后台任务（worker.py）搜索前、/同、、最、 Cookie

**、复措、**
- worker 每轮搜索前调、 inject_cookie_store_to_browser() 同、、最、 Cookie
- 后台同、、不强制刷新 m5tk（避免、、时），仅确保身、 Cookie 

---

## 五、、新增、、范的完整、、盘

### 复盘：Cookie 同名旧、、致登录态、

**时间、**
1. 用户登录后，worker 浏、、器持有、 Cookie（unb=old, cookie2=old, sgcookie=old
2. 实时搜索、 Cookie 名称、否存、  、判为已登、
3. 官方采集后来、复了这个、题（比较值）
4. 实时搜索、同、、修、  两个入口行为不一、

**根因分析**
- 登录态、查只验证"名称存在"，不验证"值一、"
- 子进程写、 JSON 后，主进程缓存未、  读到旧数、
- Cookie 写入后未推、、到 worker 浏、、器  运、、时仍用旧、

**、复措、**
- 实时搜索和官方采集统、 missing/expired/stale 三、、素、
-  CookieStore 读取前调、 invalidate_cache()
- Cookie 写入后调、 inject_cookie_store_to_worker_browser()
- BrowserManager.add_cookies() 验证改为、 Cookie 匹配

**Ԥ**
- 规范 17：身、 Cookie 必须比较值、、非仅、查存在、
- 规范 18：CookieStore 读取前必、 invalidate_cache()
- 规范 19：Cookie 写入后必须同、 worker 浏、、器上下、
- 规范 20：BrowserManager.add_cookies() 必须验证、 Cookie
- 规范 21：Cookie 注入必须通过 BrowserManager 封、
- 规范 22：后台任务搜索前必须同、 Cookie  worker

**验证方法**
- 模拟旧身、 Cookie +  JSON  实时搜索应替换注、
- 模拟子进程写、 + 主进程缓存空  健康、查应读到新数、
- 模拟抢单、 +  Cookie  应同步最、 Cookie 再执、
### 原则 1：无、编码
、有业务参数（阈、、路径、、技、栈版、、组件、、范、、能阈、、等）必须、、过配置文件管理，技能本、不含任何、编码值、

### 原则 2：可配置、
配置文件集中管理、有可变参数，、改项、结构或技、栈时、、更新配置文件，无、、改、、则文件、

### 原则 3：、用、
规则文件描述通用模式，、配不同业务场景和参数需求，提升、能的灵活性和适用性、

### 原则 4：可追溯、
每条审查发现必须包含文件、径、、号、代码片段、、严重等级、、建、、复，、保问题可定位、可、复、


---

## 、新增、、范：品牌显示与数据、致、

### 规范 23：展示层品牌必须经标题验、

**、题现、**：商品标题为"#笔、、本电脑配件 DDR4-3200-32G笔、、本内存#笔、"，但品牌列显、"联想"。根因是 task_links.display.brand 残留了旧搜索/API 推断的品牌、，详情页重采时、 detail.brand 为空而未能、、盖旧、

**根因**
- 品牌、冗余展示字、，来源于搜、 API、标题推、或历史旧、
- 详情页未识别品牌、 detail.brand=""，但原合并、、辑"仅非空才覆盖"导致旧、、保、
- 评估明细补全时直接从、 display 读取品牌，未经标题验、

**、复措、**
- 新、 normalize_display_brand() 函数，品牌必须能、当前标、、或标、、中的品牌别名验、
- extract_brand()  raw_brand 必须通过 _brand_candidate_matches_title(title) 验证
- normalize_display_fields() 、品牌推断统一、 normalize_display_brand()

**判断逻辑**
`
对于每个品牌值：
  1. 标、、是否可、
  2. 品牌、否与标、、匹配（或标题包、品牌、名）
  3. 卖、、是否更像品牌？
  4. 标、、是否能推断出品牌？
  任一答、、为、  品牌应清、
`

**适用范围**：搜、 API 解析、、情页采集、、实时搜、、官方采集、、评估明细补全、

---

### 规范 24：、情页重采必须写回空品牌

**、题现、**：点击商品链接触、 /api/items/{id}/refresh 后，品牌列仍显示旧、

**根因**：原代码仅当 detail.brand 非空时才覆盖 display.brand，空品牌、视为"无新、"而非"有效空、"

**、复措、**
- 提取统一、 sync_item_display_from_detail() 函数
- 非品牌字段：非空才、、盖（保、 seller_credit  detail 不存在的字、）
- 品牌字、：始终写回 detail.brand（空或非空）

**判断逻辑**
`
对于每个 detail 字、：
  1. 非品牌字段：detail.value 非空  覆盖 display
  2. 品牌字、：detail.brand 无、、空/非空  覆盖 display
`

**适用范围**/api/items/{id}/refresh/api/evaluations/{id}/collect-official、worker 详情阶、

---

### 规范 25：官方采集必须同、 task_links.display

**、题现、**：官方采、+评估完成后，评估事件、 items 表已更新，但 task_links.display.brand 仍为旧、

**根因**：_collect_official_and_evaluate() 更新、 items 表和评估事件，但、同、 task_links.display

**、复措、**
- 官方采集持久、 items/sellers 后，调用 sync_item_display_from_detail() 更新 display
- 、保评估明细页、 display 读取的是、新品牌、

**适用范围**：官方采集流程（api_evaluations.py  _collect_official_and_evaluate）

---

### 规范 26：评估补全前必须规范、 display

**、题现、**：即使、、情页重采已写回空品牌，评估明细页面仍显示旧品牌、

**根因**：_enrich_eval_with_item() 直接、 link_map 读取 display.brand，未经过 normalize_display_fields() 校、

**、复措、**
-  _enrich_eval_with_item() 、提取 brand 前，先、 link 数据调用 normalize_display_fields()
- 、保历史脏数据在补全阶段、纠、

**适用范围**：评估明细列表接口（/api/evaluations）、品牌过滤、、辑、

---

### 规范 27：Worker 详情阶、、不得回、到搜索摘要品、

**、题现、**：后台定时任务采集、、情后，detail.brand="" 时回、使用 summary.brand，重新写入旧品牌、

**根因**：worker.py 、使用 detail.brand or summary.brand，空品牌、视为"无、"而触发回、

**、复措、**
- Worker 详情阶、、仅使用 detail.brand
- 不回、到搜索摘要品、

**适用范围**：TaskWorker.run_once() 、的、、情阶、 display 更新、

---

### 规范 28：前、显示必须信任后、规范化数、

**、题现、**：前、尝试、行推、品牌或纠、 region/seller 错位、

**根因**：前、不理解搜、 API 字、、义的不稳定、，、行实现的校、、辑、能与后、不一致、

**、复措、**
- 前、直接使用后、 normalize_display_fields() 返回、 corrected_display
- 前、使用 field_map 驱动动、、列渲染
- 前、不实现品牌推、或字段交换、、辑

**适用范围**：商品列表、、评估明细、、实时搜索前、组件、

---

### 规范 29：前、筛、、条件必须集、管理

**、题现、**：列表刷新后分布数据、同、、更新，品牌筛、、失效、

**根因**：、个 API 调用各自维护筛、、条件，参数不一致、

**、复措、**
- 使用 filtersRef.current 集中持有、有筛选条、
-  API 调用从同、 ref 读取参数
- 筛、、条件变化时 ref 、动更、

**适用范围**：评估明细页、、商品列表页、、实时搜索页、

---

### 规范 30：fire-and-forget 副作用调度模式

**问题现象**：登录成功后会话未自动启动，需用户手动点击"启动会话"按钮

**根因**：多个登录入口各自内联副作用逻辑，部分入口遗漏调用；或使用 `await` 阻塞主流程导致登录响应延迟

**修复措施**：
- 抽离共享 helper 到独立模块（如 `web/services/session_starter.py`）
- 所有登录成功路径（QR/账密/浏览器导入/Cookie 注入）统一调用 `trigger_session_start()`
- 副作用调度使用 `asyncio.ensure_future()` 不阻塞主流程
- 失败仅记录 `logger.debug`，不抛异常（失败安全原则）
- 前端兜底提示：检测到有效 Cookie 但会话未启动时显示 warning Alert

**适用范围**：登录后自动续期、导入后自动刷新、配置变更后自动重载

**不适用场景**：同步要求的操作（必须等结果）、用户主动触发的操作、高频事件（需防抖）

**配置参数**：`config/tech-stack.json#hardConstraints.loginSideEffect`

---

### 规范 31：资源创建接口幂等性设计

**问题现象**：用户点击"启动/创建"按钮时，前端显示"启动失败"，但 UI 状态却显示"已启动"，形成错误提示与实际状态不一致的矛盾

**根因**：
- 资源创建接口（如 `/session/start`）在资源已存在时返回 `ok:False`，被前端误判为启动失败
- 实际资源已被自动启动路径（如 `trigger_session_start()` fire-and-forget）创建，状态正常
- 前端 async handler 的 else 分支显示固定失败文案，丢失后端返回的 `error` 字段

**修复措施**：
- 资源创建接口必须幂等：已是目标状态时返回 `ok:True + already_active/already_exists` 标志，不重复创建资源
- 响应结构统一用 `OperationResult` 模型（`ok` + `already_active` + `message` + `error_code`）
- 禁止用 `ok:False` 表达"已存在"语义（这是矛盾现象的根本原因）
- 必须有单元测试覆盖"首次创建 + 重复创建"两个场景

**适用范围**：所有资源创建/启动/注册接口（`session/start`、`task/create`、`connection/register` 等）；网络重试场景

**不适用场景**：纯查询接口（天然幂等）；计数器递增；一次性副作用（如发短信验证码，需用 token 防重）

**配置参数**：`config/tech-stack.json#hardConstraints.idempotentResourceCreation`

**对应审查规范**：`xianyu-backend-code-review` v4.64.0 B-REVIEW-313（IDEMPOTENT-RESOURCE-CREATION）+ B-REVIEW-314（OPERATION-RESULT-CONTRACT）

**对应测试模式**：`xianyu-auto-testing` v2.3.0 模式 AA（资源创建幂等性与状态闭环回归测试）

**对应复盘报告**：`references/retrospective-2026-07-25-r2.md` 第八轮复盘 F37

---

### 规范 32：前端 async handler 三分支完整性

**问题现象**：前端 async handler 的 else/catch 分支未刷新 UI 状态，导致 UI 显示"已启动"但后端实际失败，10 秒定时器异步同步造成"先报错后变已启动"的矛盾观感

**根因**：
- async handler 三分支（success/else/catch）状态更新逻辑不一致
- else 分支只显示固定错误文案，丢失 `result.error` 具体错误信息
- catch 分支只 `console.error`，未调用状态刷新函数

**修复措施**：
- **success 分支**（HTTP 2xx + `ok:True`）：更新 UI 状态为成功 + 调用 `loadXxx()` 刷新状态
- **else 分支**（HTTP 2xx + `ok:False`，业务失败）：显示 `result.error` 具体错误 + 调用 `loadXxx()` 刷新状态
- **catch 分支**（网络/解析异常）：显示具体错误 + 调用 `loadXxx()` 刷新状态
- 三分支必须都调用 `loadXxx()` 刷新状态，避免 UI 与后端状态矛盾
- API 函数返回类型必须与后端响应字段 1:1 对齐（如后端新增 `already_active` 字段时前端 types.ts 必须同步声明）

**适用范围**：所有触发后端写操作的 async handler（onClick/onSubmit 等）；用户操作 → API → UI 状态更新场景

**不适用场景**：纯查询 handler（无 UI 状态矛盾风险）；fire-and-forget 副作用（用规范 30 + warning Alert 兜底）

**配置参数**：`config/tech-stack.json#hardConstraints.asyncHandlerThreeBranch`

**对应审查规范**：`xianyu-frontend-code-review` v4.63.0 F-REVIEW-233（ASYNC-HANDLER-THREE-BRANCH）+ F-REVIEW-234（API-RETURN-TYPE-CONTRACT）+ F-REVIEW-235（UI-BACKEND-STATE-CONSISTENCY）

**对应测试模式**：`xianyu-auto-testing` v2.3.0 模式 AA（资源创建幂等性与状态闭环回归测试，步骤 4-5）

**对应复盘报告**：`references/retrospective-2026-07-25-r2.md` 第八轮复盘 F39/F40

---

## 七、、新增、、范的完整、、盘

### 复盘：反爬登录会话启动矛盾修复（第八轮，2026-07-25）

> 完整复盘报告：`references/retrospective-2026-07-25-r2.md`
> 配套规范：规范 31（资源创建接口幂等性设计）+ 规范 32（前端 async handler 三分支完整性）
> 配套审查：B-REVIEW-313~315（后端）/ F-REVIEW-233~235（前端）/ 模式 AA（测试）

**时间线**：
1. 用户点击"启动会话"按钮，后端 `/session/start` 返回 `ok:False`（会话已被 `trigger_session_start()` 自动启动为活跃状态）
2. 前端 `handleStartSession` 走 else 分支，显示固定文案"启动会话失败"，丢失 `result.error`
3. else/catch 分支均未调用 `loadSession()` 刷新状态，UI 仍显示旧状态"已启动"
4. 10 秒定时器异步同步状态，造成"先报错后变已启动"的矛盾观感

**根因分析（双重根因）**：
- **后端根因（F37）**：资源创建接口用 `ok:False` 表达"已存在"语义，违反幂等性设计原则
- **前端根因（F39/F40）**：async handler 三分支状态刷新不完整，else/catch 分支未调用 `loadXxx()`
- **类型根因（F38）**：API 函数返回类型与后端响应结构不匹配（`SessionStatus` vs `OperationResult`）

**修复措施**：
- 后端：`/session/start` 幂等化，会话已活跃时返回 `ok:True + already_active:True`
- 前端：`handleStartSession` 三分支（success/else/catch）都显示具体错误 + 调用 `loadSession()` 刷新状态
- 前端类型：`OperationResult` 新增 `already_active?: boolean` 字段，`startSession` 返回类型从 `SessionStatus` 改为 `OperationResult`
- 测试：补单元测试 `test_start_session_when_already_active_returns_already_active_flag`
- 文档：同步设计文档中 `/session/start` 端点的幂等行为说明

**验证方法**：
- TypeScript 类型检查（`npx tsc --noEmit`）通过
- Python ast 解析通过
- 用 code-reviewer skill 评审，结论 Approved
- 单元测试 3/3 passed（含新增幂等行为测试）

**对应规范**：规范 31（幂等性）+ 规范 32（三分支完整性）
**对应审查**：B-REVIEW-313~315 / F-REVIEW-233~235 / auto-testing 模式 AA
**完整复盘报告**：`references/retrospective-2026-07-25-r2.md`（H.1-H.7 结构）

---

### 复盘：商品品牌抓取错、与重采不更新

**时间、**
1. 商品标、、为"笔、、本电脑配件 DDR4-3200-32G笔、、本内存"，非联想品牌
2. 旧搜、/API 推断或历史数、 task_links.display.brand 、残留"联想"
3. 点击链接触发 /api/items/{id}/refresh，detail.brand="" 但因"非空才、、盖"逻辑、清旧、
4. 官方采集+评估完成后，items 表和评估事件已更新， task_links.display 、同、
5. 评估明细页面从旧 display 读取"联想"并补全到 payload.brand

**根因分析**
- 品牌验证缺失：raw brand 不经标、、验证直接传、
- 空、、义、解：detail.brand="" 、有效结果，不应、旧、、盖
- 写回、径缺失：官方采集、同、 task_links.display
- 补全、径缺失：评估 enrich 、规范、 display

**、复措、**
- 规范 23：品牌必须经标、、验、
- 规范 24：、情页重采写回空品牌
- 规范 25：官方采集同、 display
- 规范 26：评估补全前规范、 display
- 规范 27：Worker 不回、到搜索摘要品、
- 规范 28-29：前、信任后、规范化数、

**验证方法**
- 59 、相关测试全部通过
-  DB 定点、复确、 brand 已清、
- 新标题下品牌推断/清空逻辑正确

---

##  A、2026-07-22 

> 77  0  7 

### A.1 

** A、Bug  / **

|  |  |  |
|---|---|---|
| 1.  | // | API DB  |
| 2.  | service、domain、infra  | grep /  read |
| 3.  | """" |  |
| 4.  |  | Edit  Write |
| 5.  |  +  API  | pytest + curl |
| 6.  | config  | yaml_config  |

** B**

|  |  |
|---|---|
| 1.  |  hook/ |
| 2.  | // key  localStorage  yaml |
| 3.  | TS interface  |
| 4. _ | locked  1  key  |
| 5.  | title  key  hover  |

### A.2 7 2026-07 

|  |  |  |  |  |
|---|---|---|---|---|
| F1 | worker.py  NameError  | property  RiskLevel  import  | worker.py:20  import | try/except  NameError grep  |
| F2 |  0  | credit_score_min=600  0-100  | 600  60 |  |
| F3 | "" | scheduler  browser_lock  |  |  timeout/ |
| F4 |  |  width SCROLL_X  20px | width:200 + SCROLL_X:1850 |  width  ellipsis |
| F5 |  | Vite minify grep "translateDimension"  |  Python  chunk "" |  |
| F6 | PowerShell 5.1  | PS 5.1  + stdout buffer  |  Read | PS 5.1 + " + Read " |
| F7 |  |  config  |  `50 <= credit_score_min <= 100` | / |

### A.3 5 

|  |  |  |  |
|---|---|---|---|
| Bug  |  7  |  bug bug |  bug |
| / |  FieldMeta/ColumnConfig hook、dnd-kit、applyConfig、tsc、chunk  |  |  |
|  | grep  key key  titlechunk  | //reason token |  |
| / |  property vs  should_pass(threshold)worker  |  | token、auth |
|  | npm run build、Python  .js chunk |  minify  | dev server、Vite HMR  |

### A.4 8 

1. **** `responsive: ['md']`  
2. **** `try/except Exception`  NameError
3. **** `not payload.get(key)` ""
4. **** Vite minify  grep 
5. **** PowerShell 5.1 /
6. **** worker.py / scheduler.py  `get_config()` 
7. ****
8. **** SCROLL_X 50-60px 

### A.5 //

|  |  |
|---|---|
| `.trae/skills/xianyu-frontend-code-review/SKILL.md` |  A.3 "/" 4  |
| `.trae/skills/xianyu-backend-code-review/SKILL.md` |  A.2  F1/F2/F3/F7  5  |
| `.trae/skills/xianyu-auto-testing/SKILL.md` | " config "+" Python  chunk" |
| `.trae/skills/xianyu-automation-startserver/SKILL.md` | " browser_lock " |

---

##  B

- 2026-07-22
- xianyu-frontend-code-review、xianyu-backend-code-review、xianyu-auto-testing
- `docs/00-/-Z-2026-07-22.md`

---

## 附录 C：第二轮复盘参考（2026-07-22）

> 基于第二轮 Sequential Thinking 四维度复盘，新增 meta-rules #84-#89，配套审查规范 F-REVIEW-200~205 / B-REVIEW-245~250，配套测试模式 L/M/N。

详细复盘报告见独立参考文件：[retrospective-2026-07-22-r2.md](references/retrospective-2026-07-22-r2.md)

### 新增元规则速查

| # | 元规则 | 一句话概述 | 关键判断信号 | 落地位置 |
|---|---|---|---|---|
| 84 | COOKIE-TOKEN-STATE-SEPARATION | 身份 Cookie 与签名 token 分离管理，token 重置独立于 Cookie 补注入 | grep "_last_m5tk_refresh" 检查重置逻辑在补注入分支外部 | browser-automation.md / B-REVIEW-246 |
| 85 | 关键路径可观测性与状态同步三要素 | 多步骤进度编号日志 + 超时异常用户友好语义 + 组件复用状态重置 + 字段覆盖集合选择标准 | grep "asyncio.wait_for" 检查 except TimeoutError 专门分支 | error-handling.md / B-REVIEW-249 |
| 86 | SCHEDULER-STATE-MACHINE-RECOVERY | pause/resume 事件配对，暂停是循环回顶部阻塞非退出，should_pause 返回 False | grep "return True" scheduler.py 在 should_pause 分支内 | scheduler.md / B-REVIEW-245 |
| 87 | CONFIG-FIELD-FIVE-LAYER-COVERAGE | 配置字段五层链路（DB/get_config/update_config/types.ts/Config.tsx），空值删除非写空字符串 | get_config 返回字段数 < DB schema 字段数 | config-driven.md / B-REVIEW-247 |
| 88 | CROSS-LAYER-CONTRACT-SYNC | 跨层数据契约同步五步流程，空值语义区分，React 组件复用状态重置 | grep "_ALWAYS_OVERWRITE" 检查可能返回空的字段 | frontend-ui.md / B-REVIEW-248 |
| 89 | LOGIN-SIDE-EFFECT-AUTOMATION | 登录成功路径必须 fire-and-forget 调度副作用（会话续期/状态同步），失败安全不阻塞主流程 | grep "login.*success" web/routes/ 检查是否调用 trigger_session_start() | concurrency.md / B-REVIEW-250 / F-REVIEW-205 |

---

## 附录 D：第三轮复盘参考（2026-07-22）

> 基于第三轮 Sequential Thinking 四维度复盘，新增 meta-rules #90-#92，配套审查规范 F-REVIEW-206 / B-REVIEW-251~253，配套测试模式 O。

详细复盘报告见独立参考文件：[retrospective-2026-07-22-r3.md](references/retrospective-2026-07-22-r3.md)

### 新增元规则速查

| # | 元规则 | 一句话概述 | 关键判断信号 | 落地位置 |
|---|---|---|---|---|
| 90 | FALLBACK-PRESERVE-KEY 回退构造保留关联键 | 从部分数据回退构造实体时必须同时注入下游依赖的关联键 | `grep "payload.get\|fallback" src/` 检查是否遗漏 task_id | error-handling.md / B-REVIEW-251 / F-REVIEW-206 |
| 91 | TIME-WINDOW-FULL-FALLBACK 时间窗口全量回退 | 时间窗口查询无数据时必须回退到全量查询 | `grep "range_days" src/` 检查是否有回退逻辑 | database.md / B-REVIEW-252 |
| 92 | POWERSHELL-EXPLICIT-SUFFIX PowerShell 外部命令显式后缀 | PowerShell 中调用 curl/wget 必须用 .exe 后缀 | `grep "^curl " scripts/` 找到裸 curl | general-engineering.md / B-REVIEW-253 |

### v4.57.0 版本说明

- **版本号**：v4.57.0
- **更新日期**：2026-07-22
- **复盘来源**：第三轮 Sequential Thinking 四维度复盘（price_range 注入 Bug、30 天窗口无数据回退、PowerShell curl 别名冲突、端口冲突与服务未重启等 6+ 问题）
- **新增元规则**：#90-#92（3 条）
  - #90 FALLBACK-PRESERVE-KEY：回退构造保留关联键
  - #91 TIME-WINDOW-FULL-FALLBACK：时间窗口查询全量回退
  - #92 POWERSHELL-EXPLICIT-SUFFIX：PowerShell 外部命令显式后缀
- **配套审查规范**：F-REVIEW-206 / B-REVIEW-251~253
- **配套测试模式**：模式 O（回退构造关联键一致性测试）
- **下游技能同步**：xianyu-frontend-code-review / xianyu-backend-code-review / xianyu-auto-testing
- **配置驱动**：所有阈值参数通过 `config/tech-stack.json` 集中管理，无硬编码

---

## 附录 E：第四轮复盘参考（2026-07-22）

> 基于第四轮 Sequential Thinking 四维度复盘，新增 meta-rules #93-#100，配套审查规范 F-REVIEW-207~210 / B-REVIEW-254~261，配套测试模式 P/Q。
> 复盘来源：评估明细重复记录、API 响应结构变更、Worker 超时配置、BAT 编码冲突、构建环境 Node.js 版本、live_links 数据未持久化、重构后 import 缺失、排序字段填充率不足等 8 个问题。

### E.1 新增元规则速查

| # | 元规则 | 一句话概述 | 关键判断信号 | 落地位置 |
|---|---|---|---|---|
| 93 | REFACTOR-IMPORT-COMPLETENESS 重构后导入完整性 | 代码跨文件移动/提取后必须检查所有符号依赖是否完整导入 | `grep "NameError" logs/` 检查运行时缺失符号 | coding-rules/refactoring.md / B-REVIEW-254 |
| 94 | DATA-QUALITY-PRE-ASSESSMENT 数据质量前置评估 | 依赖字段做排序/过滤/聚合前必须评估数据填充率 | `SELECT COUNT(field)/COUNT(*) FROM table` 填充率 < 阈值 | coding-rules/database.md / B-REVIEW-255 |
| 95 | UPSERT-DEDUP-DEFENSE 多写入路径去重防御 | 多来源写入同一逻辑实体时必须有去重防护（DELETE+INSERT + 部分唯一索引） | `grep "save_event\|insert" src/` 多处写入同一 type | coding-rules/database.md / B-REVIEW-256 |
| 96 | DATA-FLOW-COMPLETENESS 数据流闭环 | 数据产生操作默认应持久化结果，除非显式声明为瞬态 | `grep "return.*results" src/` 检查是否缺少 DB 写入 | coding-rules/architecture.md / B-REVIEW-258 |
| 97 | API-RESPONSE-STRUCTURE-DEFENSE 外部 API 响应结构防御 | 外部 API 响应必须有结构验证/归一化层，防止第三方变更导致静默失败 | `grep "resultList\|data\[" src/` 检查硬编码路径 | coding-rules/external-api.md / B-REVIEW-257 / F-REVIEW-207 |
| 98 | BUILD-ENVIRONMENT-TOOLCHAIN-CHECK 构建环境工具链验证 | 构建脚本必须验证/设置工具链版本，避免旧版工具链导致构建失败 | `grep "npm run build\|pip install" scripts/` 缺少版本检查 | coding-rules/build.md / B-REVIEW-261 / F-REVIEW-208 |
| 99 | WORKER-TIMEOUT-PROFILE 后台任务超时档位配置 | 后台任务超时必须与操作实际耗时匹配，支持 fast/normal 多档配置 | `grep "timeout\|wait_for" src/` 检查超时值是否与操作匹配 | coding-rules/concurrency.md / B-REVIEW-259 |
| 100 | WINDOWS-SCRIPT-ENCODING Windows 脚本编码规范 | Windows 批处理脚本必须使用纯 ASCII 或与系统代码页一致的编码 | `grep "[^\x00-\x7F]" scripts/*.bat` 检查非 ASCII 字符 | coding-rules/general-engineering.md / B-REVIEW-260 |

### E.2 新增失败模式（F8-F15，2026-07 第四轮）

| 编号 | 失败现象 | 根因 | 修复 | 教训 |
|---|---|---|---|---|
| F8 | api_evaluations NameError: SellerRow | 代码跨文件移动后 import 未同步 | api_evaluations.py:13 添加 SellerRow 导入 | 重构后必须 grep 全部符号依赖 |
| F9 | publish_time 排序无效 | 97% 记录该字段为 None | 改用 refresh API 做实时搜索 + DB 写入 | 排序/过滤功能依赖字段前必须评估数据填充率 |
| F10 | eval.scored 重复写入（3×5=15） | 3 个写入路径无去重防护 | DELETE+INSERT upsert + 部分唯一索引 + C-05 迁移 | 多写入路径目标必须有 upsert + 唯一索引 |
| F11 | 闲鱼 API data.item 嵌套变更 | 第三方 API 变更结构未通知 | _search.py 添加 data.item 嵌套检测 | 外部 API 响应必须做结构验证/归一化 |
| F12 | live_links 不写入 DB | "实时"语义理解为瞬态返回 | live_links 改为写入 DB + 触发轻量评估 | 数据产生操作默认应持久化 |
| F13 | Worker 超时 30s < 搜索 45s | 超时配置与实际耗时不匹配 | 添加 fast=True 参数将搜索降至 23s | 超时必须区分 fast/normal 模式 |
| F14 | BAT 文件 GBK 乱码 | cmd.exe 用系统代码页解析 .bat | 改为纯英文脚本 | Windows 脚本避免非 ASCII 或与代码页一致 |
| F15 | Node.js 版本过旧（= 语法错误） | 系统 PATH 优先级高于项目 Node | 脚本顶部 set PATH=D:\code\nodejs24;%PATH% | 构建脚本必须验证/设置工具链版本 |

### E.3 可抽象的固定流程

**流程 6：多写入路径去重防御三件套**

```
1. 写入层：改 save_event → upsert_eval_event（DELETE+INSERT）
2. 数据库层：CREATE UNIQUE INDEX ... WHERE type = 'eval.scored'（部分唯一索引）
3. 迁移层：C-NN 清理历史重复 + 建索引（幂等，可重复执行）
```

- **适用**：评估、订单、通知等多来源写入的实体
- **不适用**：单一写入路径、需保留历史版本的实体

**流程 7：外部 API 响应归一化**

```
1. 检测响应结构版本（data.item 是否存在）
2. 提取层归一化：if "data" in item and "item" in item["data"]: item = item["data"]["item"]
3. 日志记录结构变更事件（logger.warning 附带 before/after 结构签名）
```

- **适用**：爬虫/第三方 API、无版本通知的接口
- **不适用**：内部 API（自有契约，变更可控）

**流程 8：构建环境一致性验证**

```
1. 脚本顶部设置 PATH（项目工具链优先）
2. 打印工具版本（node --version, python --version）
3. 构建后验证产物完整性（chunk 内含关键字符串）
```

- **适用**：所有生产构建脚本
- **不适用**：开发环境（nvm 等版本管理器已处理）

### E.4 适用与不适用场景

| 流程/规范 | 适用 | 不适用 |
|---|---|---|
| upsert+唯一索引去重 | 多来源写入同一逻辑实体 | 单一写入路径 |
| 数据填充率评估 | 排序/过滤/聚合依赖字段 | 纯展示字段 |
| 外部 API 归一化层 | 爬虫/第三方接口 | 内部 API |
| fast/normal 超时模式 | Worker/异步长操作 | 同步操作 |
| BAT 纯英文策略 | 含中文的 Windows 脚本 | PowerShell .ps1（UTF-8 BOM） |
| PATH 优先设置 | 构建部署脚本 | 开发环境 |

### v4.58.0 版本说明

- **版本号**：v4.58.0
- **更新日期**：2026-07-22
- **复盘来源**：第四轮 Sequential Thinking 四维度复盘（评估重复记录、API 结构变更、Worker 超时、BAT 编码、Node.js 版本、数据流闭环、重构导入缺失、数据质量评估等 8 个问题）
- **新增元规则**：#93-#100（8 条）
  - #93 REFACTOR-IMPORT-COMPLETENESS：重构后导入完整性
  - #94 DATA-QUALITY-PRE-ASSESSMENT：数据质量前置评估
  - #95 UPSERT-DEDUP-DEFENSE：多写入路径去重防御
  - #96 DATA-FLOW-COMPLETENESS：数据流闭环
  - #97 API-RESPONSE-STRUCTURE-DEFENSE：外部 API 响应结构防御
  - #98 BUILD-ENVIRONMENT-TOOLCHAIN-CHECK：构建环境工具链验证
  - #99 WORKER-TIMEOUT-PROFILE：后台任务超时档位配置
  - #100 WINDOWS-SCRIPT-ENCODING：Windows 脚本编码规范
- **配套审查规范**：F-REVIEW-207~210 / B-REVIEW-254~261
- **配套测试模式**：模式 P（评估去重验证测试）、模式 Q（构建产物验证测试）
- **下游技能同步**：xianyu-frontend-code-review / xianyu-backend-code-review / xianyu-auto-testing
- **配置驱动**：所有阈值参数通过 `config/tech-stack.json` 集中管理，无硬编码

---

## 附录 F：第五轮复盘参考（2026-07-22）

> 基于第五轮 Sequential Thinking 四维度复盘，新增 meta-rules #101-#102，配套审查规范 F-REVIEW-214~216 / B-REVIEW-267~268，配套测试模式 S/T。
> 复盘来源：Cookie 状态异常（健康状态错误显示"Cookie无效"）、页面设置持久化功能（usePersistentState Hook 实现）、CDP 模式状态刷新后丢失等 3 个问题。

### F.1 新增元规则速查

| # | 元规则 | 一句话概述 | 关键判断信号 | 落地位置 |
|---|---|---|---|---|
| 101 | MULTI-WRITE-PATH-STATE-CONSISTENCY 多写入路径状态一致性 | 验证函数依赖中间层状态时，必须检查所有写入路径是否初始化了该状态，或改为直接验证实际数据+自动同步 | `grep "_layer_states\|\.valid\|\.active" src/` 找验证函数引用的中间层状态，再 `grep` 所有写入入口检查是否调用初始化 | state-management.md / B-REVIEW-267 / F-REVIEW-214 |
| 102 | UI-PREFERENCE-PERSISTENCE-UNIFIED UI偏好统一持久化 | 用户可配置的UI偏好（pageSize/viewMode/filter/开关）必须使用 usePersistentState 而非 useState | `grep "useState" frontend/src/pages/` 检查变量名是否是用户偏好（pageSize/viewMode/filter/Enabled/Mode），是则改用 usePersistentState | frontend-ui.md / F-REVIEW-215 / F-REVIEW-216 |

### F.2 新增失败模式（F16-F18，2026-07 第五轮）

| 编号 | 失败现象 | 根因 | 修复 | 教训 |
|---|---|---|---|---|
| F16 | Cookie 有效但健康状态显示"无效" | cookie_checker 依赖 CookieRotator._layer_states.valid，但 5 个登录写入路径中 4 个未调用 on_login_success/atomic_update 初始化层状态 | 重写 cookie_checker 基于实际 Cookie 内容判断 + 新增 sync_state_from_cookies 自动同步层状态 | 验证函数不应仅依赖中间层状态，应基于实际数据判断 |
| F17 | 页面刷新后 UI 偏好（pageSize/viewMode/filter）丢失 | 各组件用 useState 管理 UI 偏好，无持久化机制；已有持久化分散在各组件（ThemeContext/ItemList/TaskEditor），错误处理不一致 | 创建统一 storage 工具 + usePersistentState Hook，各页面替换 useState | UI 偏好必须统一持久化，避免分散实现导致错误处理不一致 |
| F18 | CDP 模式开关刷新后恢复为关闭 | AntiCrawl/index.tsx 用 useState(false) 管理 CDP 开关，无持久化 | 替换为 usePersistentState | 新增 UI 开关时必须考虑持久化需求 |

### F.3 可抽象的固定流程

**流程 9：多写入路径状态一致性检查**

```
1. 识别验证函数依赖的中间层状态（grep .valid/.active/_layer_states）
2. 列出所有写入目标数据的入口点（grep export_cookies/on_login_success/atomic_update）
3. 检查每个入口是否调用了状态初始化函数
4. 若有遗漏：
   a. 补全调用（推荐），或
   b. 改为直接验证实际数据 + 提供自动同步方法修复不一致
5. 添加自动同步机制（sync_state_from_xxx），在验证时自动修复不一致
```

- **适用**：健康检查接口、状态检查接口、依赖运行时内存状态的验证函数
- **不适用**：单一写入路径、纯数据验证（无中间层状态）、瞬态状态

**流程 10：UI 偏好持久化三层架构**

```
1. 底层：storage 工具（get/set/remove + 数据验证 + 错误处理 + 内存回退 + 版本管理）
2. 中层：usePersistentState Hook（useState 兼容 API + 防抖写入 + isPersistent 标识 + remove 方法）
3. 上层：各页面用 usePersistentState 替换 useState（配置 validator + 调整 debounce）
```

- **适用**：用户可配置的 UI 偏好（pageSize/viewMode/filter/开关/主题）
- **不适用**：loading 状态、modal 开关、搜索关键词、表单数据（除非草稿）、敏感数据

### F.4 适用与不适用场景

| 流程/规范 | 适用 | 不适用 |
|---|---|---|
| 多写入路径状态一致性检查 | 健康检查、状态检查、依赖运行时状态的验证 | 单一写入路径、纯数据验证 |
| UI 偏好统一持久化 | 分页大小、视图模式、筛选条件、开关偏好 | loading、modal、搜索词、敏感数据 |
| storage 工具统一错误处理 | 所有 localStorage 操作 | SSR 环境、大量数据存储 |

### v4.60.0 版本说明

- **版本号**：v4.60.0
- **更新日期**：2026-07-22
- **复盘来源**：第五轮 Sequential Thinking 四维度复盘（Cookie 状态异常、页面设置持久化、CDP 模式状态丢失等 3 个问题）
- **新增元规则**：#101-#102（2 条）
  - #101 MULTI-WRITE-PATH-STATE-CONSISTENCY：多写入路径状态一致性
  - #102 UI-PREFERENCE-PERSISTENCE-UNIFIED：UI偏好统一持久化
- **配套审查规范**：F-REVIEW-214~216 / B-REVIEW-267~268
- **配套测试模式**：模式 S（UI 偏好持久化回归测试）、模式 T（多写入路径状态一致性测试）
- **下游技能同步**：xianyu-frontend-code-review / xianyu-backend-code-review / xianyu-auto-testing
- **配置驱动**：所有阈值参数通过 `config/tech-stack.json` 集中管理，无硬编码

---

### v4.61.0 版本说明

- **版本号**：v4.61.0
- **更新日期**：2026-07-22
- **复盘来源**：第六轮 Sequential Thinking 四维度复盘（React SPA 间歇性白屏修复）
- **新增元规则**：#95（1 条）
  - #95 SPA-RENDER-RESILIENCE：SPA 渲染容错体系
- **新增 steps**：step 254-261（8 条，frontend-ui.md 5 条 + testing.md 3 条）
- **配套审查规范**：F-REVIEW-217~221
- **配套测试模式**：模式 U（SPA 渲染容错回归测试）、模式 V（测试环境预检回归测试）
- **下游技能同步**：xianyu-frontend-code-review / xianyu-auto-testing
- **配置驱动**：所有阈值参数通过 `config/tech-stack.json#hardConstraints.spaRenderResilience` 集中管理，无硬编码

---

## 阶段交接声明

- 当前阶段：v4.62.0 四维度复盘编码规范沉淀 ✅ 已完成
  - 新增 meta-rule #95（SPA 渲染容错体系）
  - 新增 step 254-261（全局 ErrorBoundary / lazyRetry / 路由级 ErrorBoundary / API 防御性兜底 / 401 防抖 / Vitest 预检 / tsconfig 排除测试文件 / antd 中文按钮空格兼容）
  - 新增失败模式 F19-F26（ErrorBoundary 缺失/chunk 失效/未保护数据访问/401 硬跳转/路由错误无隔离/vitest 卡死/tsconfig 未排除/antd 空格）
  - 复盘来源：React SPA 间歇性白屏修复（2026-07-22）
  - 根因：缺少全局 ErrorBoundary / 懒加载 chunk 无重试 / 未保护数据访问 / 401 硬跳转 / 路由错误无隔离
- 下一阶段：v4.62.0 规划
- 下一阶段智能体：bemp-personalized-developer 或 xianyu 代码审查相关智能体
- 下一阶段技能：xianyu-hunter-dev / xianyu-frontend-code-review / xianyu-backend-code-review
- 交接上下文：基于"React SPA 间歇性白屏"问题修复后四维度复盘（Sequential Thinking），新增 meta-rule #95 和 step 254-261，沉淀"渲染容错三件套分层防御 / 懒加载 chunk 失效重试 / 401 拦截器防抖与 replace 跳转"三条可抽象流程。所有阈值参数通过 `config/tech-stack.json#hardConstraints.spaRenderResilience` 集中管理，无硬编码。同步在前端审查新增 F-REVIEW-217~221、auto-testing 新增模式 U（SPA 渲染容错回归测试）和模式 V（测试环境预检回归测试）。

### v4.62.0 版本说明

- **版本号**：v4.62.0
- **更新日期**：2026-07-23
- **复盘来源**：基于12个历史问题的四维度复盘，提炼6条新编码规范
- **新增 steps**：
  - step 253：缓存守卫三原则（CACHE-GUARD-3RULES，meta-rule #104 落地）→ config-driven.md
  - step 248：数据写入策略字段级决策规范（FIELD-STRATEGY-01，meta-rule #105 落地）→ general-engineering.md
  - step 249：回调注入默认值模式规范（CALLBACK-INJECTION-01，meta-rule #106 落地）→ general-engineering.md
  - step 259：UI视觉变更预确认门控规范（UI-PREVIEW-GATE-01，meta-rule #103 落地）→ frontend-ui.md
  - step 260：React状态选型判断矩阵规范（STATE-SELECTION-01，meta-rule #107 落地）→ frontend-ui.md
  - step 245：状态机返回值语义校验规范（STATE-MACHINE-RETURN-01，meta-rule #109 落地）→ state-management.md
- **配置驱动**：所有阈值参数通过 `config.yaml` 集中管理，无硬编码

---

## 附录 G：第七轮复盘参考（2026-07-25）

> 基于第七轮 Sequential Thinking 四维度复盘（智能客服 Markdown 渲染与 follow_ups 推荐问题代码评审，发现 10 个问题），新增 coding-standards v1.3 §2.21-2.24（后端 LLM 治理）+ §3.10-3.15（前端韧性），配套审查规范 B-REVIEW-291~294 / F-REVIEW-227~232，配套测试模式 Y/Z。

详细复盘报告见独立参考文件：[retrospective-2026-07-25.md](references/retrospective-2026-07-25.md)

### 新增编码规范速查

| 规范编号 | 规范名称 | 一句话概述 | 关键判断信号 | 落地位置 |
|---|---|---|---|---|
| §2.21 | LLM 附加调用预算与用量闭环 | 附加 LLM 调用必须共享主调用 BudgetContext，前 check_budget 后 _record_llm_usage | grep "generate_follow_ups" 检查是否有 check_budget | coding-standards.md / B-REVIEW-291 |
| §2.22 | LLM 附加调用独立超时 | 附加调用必须用 asyncio.wait_for 设置独立超时 < 主调用超时 | grep "asyncio.wait_for" 检查附加调用 | coding-standards.md / B-REVIEW-292 |
| §2.23 | LLM 响应结构化解析 | 禁止正则提取 JSON，必须 json.loads + 类型校验 + 代码块剥离 | grep "re.search.*\\\\{.*\\\\}" 找违规 | coding-standards.md / B-REVIEW-293 |
| §2.24 | LLM 多调用一致性 | 附加调用异常处理/日志/降级与主调用一致，异常不冒泡 | grep "except" 检查附加调用异常处理 | coding-standards.md / B-REVIEW-294 |
| §3.10 | Markdown 预处理代码块保护 | 替换前必须分割代码块，仅对非代码段执行替换 | grep "content.replace" 检查是否分割 | coding-standards.md / F-REVIEW-227 |
| §3.11 | React render 阶段副作用禁令 | render 阶段禁止写 ref，必须在 useEffect 中 | grep ".current =" 检查上下文 | coding-standards.md / F-REVIEW-228 |
| §3.12 | SSE 事件运行时类型校验 | 禁止 as 断言，必须 zod safeParse + fallback | grep "as string\[\]" 找违规 | coding-standards.md / F-REVIEW-229 |
| §3.13 | 定时器清理与竞态防护 | 卸载时清理 + 重设前清除旧定时器 + useRef 存储 ID | grep "setTimeout" 检查 cleanup | coding-standards.md / F-REVIEW-230 |
| §3.14 | 交互元素可访问性 | 非原生交互元素三件套：tabIndex/role/onKeyDown | grep "<div onClick" 检查三件套 | coding-standards.md / F-REVIEW-231 |
| §3.15 | 流式响应 onComplete 数据完整性 | 持久化判断基于任一产出非空，禁止单字段判断 | grep "content.length > 0" 检查条件 | coding-standards.md / F-REVIEW-232 |
| §2.25 | 预设切换双步模式与归档加载契约 | 切换预设必须传 `from_preset`+`to_preset` 双参数，后端原子归档-加载并返回脱敏 Key | grep "applyPreset\|apply-preset" 检查参数个数 | coding-standards.md / B-REVIEW-327 / F-REVIEW-243 |
| §2.26 | 敏感数据后端主导原则 | 敏感数据存储位置由后端决定，比较用 `hmac.compare_digest`，写入失败告警，日志禁打值 | grep "== .*token\|provided_token ==" 找直接比较 | coding-standards.md / B-REVIEW-328 / B-REVIEW-329 |

### v4.67.0 版本说明
- **新增编码规范**：coding-standards §2.27（类型注解契约对齐规范）+ step 273（TYPE-ANNOTATION-CONTRACT-ALIGNMENT-01，meta-rule #110 落地 experimental）
- **配套审查规范**：B-REVIEW-330（后端函数返回类型注解与 Pydantic ResponseModel 一致性）/ F-REVIEW-244（前端 types.ts 与后端返回结构对齐）
- **配套测试模式**：模式 AE（类型注解契约对齐回归测试）
- **下游技能同步**：xianyu-backend-code-review v4.66.0（type_annotation_contract 节点）/ xianyu-frontend-code-review v4.66.0（type_annotation_contract 节点）/ xianyu-auto-testing v2.6.0（新增模式 AE）
- **配置驱动**：复杂返回类型列表、权威源优先级、观察期、升正阈值通过 `tech-stack.json#hardConstraints.typeAnnotationContract` 集中管理，无硬编码
- **关键决策**：① experimental 标记 + 1 季度观察期（2026-10-26 截止）+ 升正阈值 2 次 ② 权威源优先级：Pydantic ResponseModel > 前端 types.ts > 后端函数类型注解 ③ 单元测试必须断言完整结构（字段名 + 字段类型 + 至少一个字段的值），仅断言长度视为违规
- **复盘报告**：[retrospective-2026-07-26.md](references/retrospective-2026-07-26.md)

### v4.66.0 版本说明
- **新增编码规范**：coding-standards §2.25（预设切换双步模式与归档加载契约）+ §2.26（敏感数据后端主导原则）
- **配套审查规范**：B-REVIEW-327~329（后端预设切换与状态回传契约）/ F-REVIEW-241~243（前端 UI 状态映射与链接安全）
- **下游技能同步**：xianyu-backend-code-review v4.45.0（preset_and_status_contract 节点）/ xianyu-frontend-code-review v4.66.0（ui_state_and_link_safety 节点）/ xianyu-auto-testing v2.5.0（新增 AB/AC 模式后的测试连接断言点补充）
- **配置驱动**：预设定义保留在前端 `constants.ts`（业务参数），审查阈值/正则/方法名通过 `config.yaml` 集中管理，无硬编码
- **关键决策**：① 预设定义前后端分离（前端持预设列表，后端通过 `apply-preset` 接口接收参数执行） ② 敏感数据后端主导（前端只发送不持久化明文） ③ 测试接口状态回传契约（避免前端额外查询） ④ HF 缓存轻量检测（目录存在性而非模型实例化）

### v4.63.0 版本说明

- **版本号**：v4.63.0
- **更新日期**：2026-07-25
- **复盘来源**：第七轮 Sequential Thinking 四维度复盘（智能客服 Markdown 渲染与 follow_ups 推荐问题代码评审，10 个问题）
- **新增编码规范**：coding-standards v1.3 §2.21-2.24（后端 LLM 治理 4 条）+ §3.10-3.15（前端韧性 6 条）
- **配套审查规范**：B-REVIEW-291~294（后端 LLM 治理）/ F-REVIEW-227~232（前端韧性）
- **配套测试模式**：模式 Y（前端韧性回归测试）/ 模式 Z（LLM 治理回归测试）
- **下游技能同步**：xianyu-backend-code-review v4.62.0 / xianyu-frontend-code-review v4.62.0 / xianyu-auto-testing v2.2.0
- **配置驱动**：所有阈值/正则/方法名/文件路径通过 `config.yaml` 集中管理，无硬编码
- **复盘报告**：[retrospective-2026-07-25.md](references/retrospective-2026-07-25.md)

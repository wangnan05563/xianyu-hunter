# 维度 43：可选依赖完整性与降级契约 🆕v4.70.0

> **编码规范引用**：xianyu-hunter-dev `references/deployment-runtime-standards.md` 规范 S3
> **配置节点**：config.yaml#coding_standards.optional_dependency
> **测试关联**：xianyu-auto-testing 模式 Q（构建产物）/ E（pytest 环境）

## 触发条件
- 修改 `container.py` 中任何"可选依赖"模块的初始化（`except ImportError / Exception` 兜底返回 `None`）
- venv 重建、Python 版本切换、pip 中断后排查"模块未启用"
- 任何依赖 `chromadb` / `sentence-transformers` / 间接 `grpcio` 等可选组件的功能

## 检查规则

### 强制（P1 严重）
- 可选模块初始化失败时，**必须显式降级**：返回 `None` + 明确日志（如 `可选依赖缺失，跳过初始化: <原因>`），不得静默 `except: pass` 也不得 fail-fast 拖垮整个应用。
- 降级时后端对应端点必须返回**明确禁用码**（如 `403 CHATBOT_DISABLED`），而非 500 或空响应，使前端能区分"未启用"与"系统错误"。
- 前端对禁用码的处理应为预期行为（`getConfig()` 失败 `.catch(() => null)` → `message.error('模块未启用或加载失败')`），不应视为崩溃。

### 推荐（P2 改进）
- 在依赖导入处写明"缺失时如何安装"（`pip install <pkg>`），降低排查成本。
- `container.py` 的兜底日志应区分 `ImportError`（依赖缺失）与逻辑 `Exception`（初始化 bug），便于定位。

### 禁止
- 必选依赖缺失时仍走"降级"路径（必选依赖应 fail-fast）。
- 把"环境损坏导致的导入失败"误报为"业务禁用"。

## Grep 扫描命令
```bash
# 检测可选模块初始化是否有显式降级与日志
grep -n "可选依赖\|ImportError\|跳过初始化\|CHATBOT_DISABLED" src/xianyu_hunter/container.py

# 验证 venv 依赖是否可导入（独立于代码，用于环境排查）
.venv/Scripts/python.exe -c "import chromadb, grpc; print('ok')"
```

## 判断标准
- 可选模块失败时无日志/静默 → P1 严重
- 禁用时返回 500/空而非明确禁用码 → P1 严重
- 必选依赖误走降级 → P0 阻塞

## 适用场景
- `container.py` 的 `except ImportError / Exception` 兜底
- 任何"依赖缺失不应拖垮全局"的可选功能（智能客服、可选浏览器后端等）

## 不适用场景
- 必选依赖（核心运行所需）：缺失应 fail-fast，不适用降级契约
- 纯前端单测（vitest）：不涉及 venv 依赖
- 已确认依赖永远存在的 Docker 生产镜像（但本地/CI 开发环境仍建议保留降级契约）

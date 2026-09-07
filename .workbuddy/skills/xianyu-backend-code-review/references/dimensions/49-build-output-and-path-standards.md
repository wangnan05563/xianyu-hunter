# 维度 49：构建打包与路径标准（release 集中化 / SPA 单一来源 / 路径溯源 / 沙箱安全删除 / 路径零硬编码）🆕v4.73.0 · B-REVIEW-342

> **编码规范引用**：xianyu-hunter-dev 规范 29（构建产物集中到 release/）/ 规范 30（SPA 单一来源）/ 规范 31（路径溯源消除魔法数）/ 规范 32（沙箱安全删除范式）/ 规范 33（配置与路径零硬编码）
> **配置节点**：config.yaml#build_output_standards（新增）
> **测试关联**：xianyu-auto-testing 模式 AO（release 构建路径一致性）/ 模式 AP（沙箱安全删除）
> **复盘来源**：retrospective-2026-08-16-release-centralization（案例 release 根统一 / SPA 单一来源 / parents[3] 魔法数 / safe-delete 守卫 + 流程 A–E）

## 触发条件
- 修改 `scripts/build-exe.ps1` 的 PyInstaller `--distpath` / `--workpath`
- 修改 `backend/xianyu_hunter/web/app.py` 的 SPA 伺服路径
- 修改 `backend/xianyu_hunter/paths.py` 的路径溯源（新增/改 `get_project_root()`）
- 出现 `dist\xianyu-hunter`、`parents[3]` 魔法数、`backend/.../static/spa` 兜底、脚本内 `rm`/`del`/`Remove-Item` 删除
- 切换产品输出根或前端 base path

## 检查规则

### 强制（P0 阻塞）
- `build-exe.ps1` 必须把 PyInstaller 的 `--distpath` 与 `--workpath` 统一到 `release/`（`release/xianyu-hunter` 为真正出货 exe，`release/.work` 为中间产物）；禁止散落 `dist/` / `build/` 作为产出根。
- `app.py` 伺服 SPA 的路径必须来自 `get_project_root() / "release" / "spa"`（vite 权威输出）；**禁止** `Path(__file__).resolve().parents[3]` 之类魔法数；**禁止** `backend/.../static/spa` 兜底目录（已删除，重复来源会导致陈旧 hash chunk 混入安装包）。
- 构建/清理脚本中的删除必须绕过沙箱 safe-delete 守卫（fail-closed 会中断脚本）：PowerShell 用 `[System.IO.Directory]::Delete($p, $true)` / `[System.IO.File]::Delete($p)`；Python 用 `ctypes.windll.kernel32.RemoveDirectoryW` / `DeleteFileW`。**禁止** `rm` / `del` / `Remove-Item`（命中即 P0 警告，须改为 .NET/ctypes 调用）。

### 推荐（P1 严重）
- 产品输出根（release/）、base path、构建参数全部走配置（vite `base` / `build-exe.ps1` 变量 / `installer.iss` OutputDir 派生），禁止散落绝对盘符路径（如 `D:\...\dist`）。
- 改输出根 / base path 时，相关七处路径引用（vite outDir / build-exe --distpath / installer OutputDir / 部署复制源 / app.py 伺服路径 / 子脚本默认路径 / cleanup+gitignore）必须同步对齐（见规范 29 判断逻辑）。

### 推荐（P2 改进）
- KB 索引排除清单里的 `dist`/`build` 字面量语义为“被排除目录名”，与构建产物目录同名但含义不同，审查时**不得盲目替换**，需区分保留。
- 大目录删除（超批量阈值）应走同卷 `os.rename` 逃逸（O(1)）或分片批量（≤120/批 + ≥6s 暂停），避免沙箱内核级限速 kill 整进程。

## Grep 扫描命令
```bash
# 检测 build-exe.ps1 是否统一 distpath/workpath 到 release/
grep -n "distpath\|workpath" scripts/build-exe.ps1

# 检测 app.py SPA 伺服路径是否来自 get_project_root()/release/spa（应无 parents[3] / backend/.../static/spa）
grep -n "parents\[3\]\|static/spa\|get_project_root" backend/xianyu_hunter/web/app.py backend/xianyu_hunter/paths.py

# 检测脚本删除是否绕过 safe-delete（应无 rm/del/Remove-Item）
grep -rn "Remove-Item\|\brm\b\|\bdel\b" scripts/build-exe.ps1 scripts/启动服务.bat

# 检测残留 dist\xianyu-hunter 陈旧引用（应清零）
grep -rn "dist\\\\xianyu-hunter\|dist\\\\XianyuHunter-Setup" scripts/ backend/ --include="*.ps1" --include="*.bat" --include="*.py"
```

## 判断标准
- build-exe 未统一 distpath/workpath 到 release/ → P0 阻塞
- app.py SPA 伺服用 parents[3] 魔法数或 backend/.../static/spa 兜底 → P0 阻塞
- 脚本删除用 rm/del/Remove-Item 未改 .NET/ctypes 调用 → P0 警告（必须改）
- 输出根 / base path 写死绝对盘符路径 → P1 严重
- 七处路径引用未同步对齐 → P1 严重

## 适用场景
- 桌面 PyInstaller 打包项目（exe 从磁盘加载前端）
- 任何构建产物集中归档发布、需跨多脚本保持输出根一致的项目
- 本沙箱（safe-delete 守卫）下的构建/清理脚本删除

## 不适用场景
- 纯后端 JSON API（无 SPA 打包 → 维度 49 打包侧动作不适用，但路径零硬编码原则仍适用）
- 非本沙箱环境（无 safe-delete 守卫 → 删除可简化，但单一来源/路径溯源原则仍适用）
- 纯前端 SPA（无 PyInstaller 打包 → release 打包侧动作不适用）

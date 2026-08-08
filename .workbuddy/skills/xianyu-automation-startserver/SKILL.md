---
name: "xianyu-automation-startserver"
description: "闲鱼猎人（XianyuHunter）项目服务生命周期自动化管理：启动/停止/重新构建/环境检查/状态查询，含环境预检查、日志记录、失败回滚。当用户要求'启动/开始/运行/起一下/打开/跑起来'闲鱼猎人服务，'停止/关闭/退出/停一下/关掉'服务，'重新构建/重新编译/rebuild'前端，'检查环境/看看环境就绪没/环境是否OK'，或提到'xianyu-automation-startserver / 闲鱼猎人 启动 停止 重建'时调用。仅管理闲鱼猎人项目自身服务生命周期；其他项目或系统级服务请用 RunCommand 直接操作。"
whenToUse: "用户要求启动/停止/重新构建闲鱼猎人项目服务，或检查项目运行环境是否就绪、查询服务当前状态（8000 端口/PID）"
triggers:
  - "启动/开始/运行/起一下/打开/跑起来 闲鱼猎人/XianyuHunter/xianyu 服务/web"
  - "停止/关闭/退出/停一下/关掉 闲鱼猎人 服务"
  - "重新构建/重新编译/rebuild 闲鱼 前端/vite"
  - "检查/看看 闲鱼 项目 环境/依赖 就绪/是否OK"
  - "闲鱼 服务 状态/端口/PID 查询"
  - "xianyu-automation-startserver / 闲鱼猎人 启动 停止 重建"
version: "1.0.0"
updated: "2026-07-07"
---

# Xianyu Automation StartServer

整合 `scripts\启动服务.bat`、`scripts\停止服务.bat`、`scripts\重新构建.bat` 三个脚本，提供闲鱼猎人项目的自动化生命周期管理。

## 何时触发

满足以下任一条件即应调用本技能：

- 用户要求"启动 / 开始 / 运行"闲鱼猎人、XianyuHunter、xianyu web 服务
- 用户要求"停止 / 关闭 / 退出"闲鱼猎人服务
- 用户要求"重新构建 / 重新编译 / rebuild"前端
- 用户要求检查项目环境是否就绪
- 用户明确提到 `xianyu-automation-startserver` 技能名

## 支持的动作

| 动作 | 命令 | 说明 |
|------|------|------|
| 启动 | `start` | 环境检查 → 调用 `启动服务.bat` → 验证 8000 端口 |
| 停止 | `stop` | 调用 `停止服务.bat` → 验证端口已释放 |
| 重新构建 | `rebuild` | 停止 → 调用 `重新构建.bat` → 启动 |
| 环境检查 | `check` | 仅执行依赖与配置检查，不启动服务 |
| 状态查询 | `status` | 查询 8000 端口与 PID 文件状态 |

## 执行入口

**统一通过 PowerShell 调用自动化脚本**（不要直接调用 .bat，由脚本内部按序调用）：

```powershell
# 在项目根目录执行
powershell -ExecutionPolicy Bypass -File scripts\automation.ps1 -Action <start|stop|rebuild|check|status>
```

参数说明：
- `-Action`：必填，取值见上表
- `-LogFile`：可选，默认 `logs\automation.log`

## 执行流程

### 1. 启动 (start)

1. **环境预检查**（失败立即终止，不调用 .bat）：
   - `.venv\Scripts\python.exe` 存在
   - `frontend\node_modules\vite\bin\vite.js` 存在（前端已构建过）
   - `config\config.yaml` 存在（或 `config.example.yaml` 已被复制）
   - `.env` 存在（或 `.env.example` 已被复制）
   - `D:\code\nodejs24\node.exe` 存在（构建用 Node.js）
2. **调用** `scripts\启动服务.bat`
3. **验证**：等待最多 30 秒，检查 8000 端口是否监听
4. **记录** PID 到 `logs\web.pid`（由 .bat 完成）
5. **失败回滚**：若 30 秒未启动，提示检查 `logs\web.log` 与 `logs\web.err`

### 2. 停止 (stop)

1. **调用** `scripts\停止服务.bat`
2. **验证**：检查 8000 端口已释放、`logs\web.pid` 已删除
3. **失败提示**：若端口仍被占用，提示用户手动检查任务管理器

### 3. 重新构建 (rebuild)

按依赖顺序串联执行：

1. **Step 1 停止**：调用 `scripts\停止服务.bat`（必须先停服，否则 vite 构建会失败或文件锁定）
2. **Step 2 构建**：调用 `scripts\重新构建.bat`（内部会清理 `src\xianyu_hunter\web\static\spa` 并执行 vite build + build_info.py）
3. **Step 3 启动**：调用 `scripts\启动服务.bat`
4. **任一步失败**：立即终止后续步骤，输出失败位置与日志路径
   - Step 1 失败：提示端口冲突，不进入构建
   - Step 2 失败：不启动服务，提示前端构建错误，需排查 `frontend\` 目录
   - Step 3 失败：保留构建产物，提示检查后端日志

## 环境检查清单 (check 动作)

按以下顺序检查并输出 ✅ / ❌：

1. Python 虚拟环境：`.venv\Scripts\python.exe`
2. Python 核心依赖：能 `import xianyu_hunter, uvicorn, fastapi`
3. Node.js 24：`D:\code\nodejs24\node.exe --version`
4. 前端依赖：`frontend\node_modules\vite\bin\vite.js`
5. 配置文件：`config\config.yaml`
6. 环境变量：`.env`
7. 日志目录：`logs\`（不存在则创建）
8. PID 文件状态：`logs\web.pid` 是否存在及其对应进程是否存活
9. 8000 端口状态：是否被占用

## 日志记录

所有操作写入 `logs\automation.log`，每行格式：

```
2026-07-04 10:30:15 [INFO]  ACTION=start STEP=env-check RESULT=pass
2026-07-04 10:30:16 [INFO]  ACTION=start STEP=call-bat RESULT=pass
2026-07-04 10:30:45 [ERROR] ACTION=start STEP=verify-port RESULT=fail MSG="port 8000 not listening after 30s"
```

字段说明：
- `ACTION`：start / stop / rebuild / check / status
- `STEP`：env-check / call-bat / verify-port / verify-stop / build / clean
- `RESULT`：pass / fail / skip
- `MSG`：失败时的额外信息

## 用户交互接口

AI 智能体在触发本技能时，应：

1. **明确动作**：从用户指令中识别 start/stop/rebuild/check/status，若模糊则用 `AskUserQuestion` 确认
2. **执行前确认**：对 `rebuild` 动作，需提示用户"将停止当前服务并重新构建前端，确认继续？"
3. **执行中反馈**：每个步骤完成后输出简短进度（如 `[2/3] 构建前端...`）
4. **执行后总结**：输出最终状态、访问地址（http://127.0.0.1:8000/app/）、日志路径

## Windows 兼容性要点

- 所有路径使用反斜杠 `\`
- PowerShell 不支持 `&&`，串联命令使用 `;` 或换行
- 调用 .bat 时使用 `cmd /c` 包裹，避免 PowerShell 解析 .bat 中的 `&` 等特殊字符
- 中文脚本名（`启动服务.bat` 等）需指定 UTF-8 编码：`chcp 65001` 或 PowerShell 5.x 中使用 `-Encoding UTF8`
- 进程清理使用 `taskkill /F /T /PID`，递归终止子进程

## 错误处理与回滚

| 错误场景 | 处理方式 |
|---------|---------|
| `.venv` 不存在 | 输出修复命令：`python -m venv .venv` 后终止 |
| Python 依赖缺失 | 输出：`.venv\Scripts\pip install -r requirements.txt` 后终止 |
| Node.js 不存在 | 提示安装 Node.js 24 或检查 `D:\code\nodejs24\` 路径 |
| 8000 端口被未知进程占用 | 列出占用 PID，提示用户确认后用 `停止服务.bat` 或手动 `taskkill` |
| 构建失败 | 保留旧 `spa` 目录（如有备份），提示检查 vite 错误输出 |
| 启动 30 秒后端口未监听 | 输出 `logs\web.log` 末尾 20 行，提示后端启动错误 |

## 使用示例

**用户**："启动闲鱼猎人"
**AI**：识别为 `start` 动作 → 执行环境检查 → 调用 `scripts\automation.ps1 -Action start` → 输出访问地址

**用户**："重新构建前端"
**AI**：识别为 `rebuild` 动作 → 用 `AskUserQuestion` 确认 → 执行 stop → build → start 三步 → 报告结果

**用户**："检查环境"
**AI**：识别为 `check` 动作 → 执行 `scripts\automation.ps1 -Action check` → 输出 9 项检查清单

## 文件清单

| 文件 | 用途 |
|------|------|
| `.trae\skills\xianyu-automation-startserver\SKILL.md` | 本技能指南 |
| `scripts\automation.ps1` | PowerShell 自动化执行器 |
| `scripts\启动服务.bat` | 启动服务原始脚本 |
| `scripts\停止服务.bat` | 停止服务原始脚本 |
| `scripts\重新构建.bat` | 重新构建原始脚本 |
| `logs\automation.log` | 自动化操作日志 |

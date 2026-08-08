# A. 环境核查

> 对应决策节点：DT-01（web 进程未运行）、DT-02（构建产物缺失或过期）

## 检查项

### A1. Web 进程状态

读取 `config.yaml` 的 `web_process` 段：
- `port`：监听端口
- `host`：监听地址
- `process_name_pattern`：进程名匹配
- `cmdline_pattern`：命令行匹配

**PowerShell 命令**：

```powershell
# 检查端口监听
netstat -ano | Select-String ":<port>"

# 检查进程
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match '<process_name_pattern>' -and $_.CommandLine -match '<cmdline_pattern>' } |
  Select-Object ProcessId, CreationDate, CommandLine |
  Format-List
```

**判断**：
- 端口未监听 → DT-01 命中
- 进程 CommandLine 不包含 `cmdline_pattern` → 不是本项目的 web 进程
- 进程 CreationDate 与构建产物时间戳对比 → 用于 DT-02 判断

### A2. 构建产物状态

读取 `config.yaml` 的 `project.build_output_dir` 和 `build.fs_sync_delay_sec`：

```powershell
# 检查构建产物目录是否存在
if (Test-Path <build_output_dir>) {
  Get-ChildItem <build_output_dir> -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 5 Name, LastWriteTime, Length
} else {
  Write-Output 'build output directory does not exist'
}
```

**判断**：
- 目录不存在 → DT-02 命中
- 最新文件时间戳 < web 进程启动时间 → DT-02 命中（web 加载的是旧版本）
- 时间戳正常 → 进入下一检查

### A3. 关键产物文件清单

应存在的文件（在 `build_output_dir` 下）：
- `index.html`（SPA 入口）
- `<pwa.sw_filename>`（Service Worker）
- `<pwa.workbox_filename_prefix>*.js`（Workbox 运行时）
- `manifest.webmanifest`（PWA 清单）
- `assets/` 目录（构建产物 chunks）

**注意**：构建产物路径不是默认的 `frontend/dist`，而是 `<project.build_output_dir>`（由 `key_files.vite_config` 的 outDir 指定）。这是该项目特有的配置，不要假设默认路径。

## 命中后动作

- DT-01 命中：按 `web_process.start_command` 启动 web 进程
- DT-02 命中：按 `build.command` 重新构建，然后重启 web 进程

## 输出报告

执行完环境核查后，报告：
1. Web 进程状态（PID、启动时间、命令行）
2. 构建产物路径与最新文件时间戳
3. 时间戳对比结论（web 是否加载最新版本）
4. 命中的决策节点 ID

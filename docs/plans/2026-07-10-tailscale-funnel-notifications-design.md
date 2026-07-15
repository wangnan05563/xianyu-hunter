# Tailscale Funnel 与隧道启动通知设计

## 目标

在现有 Cloudflare Tunnel 和 cpolar 之外增加 Tailscale Funnel Provider，并复用现有的一键启动、停止、状态查询和开机自启动能力。任一 Provider 成功获得公网 URL 后，通过当前已启用的统一通知渠道发送一条可直接打开地址的通知；钉钉使用 ActionCard 按钮。

## 架构

`TailscaleProvider` 继续实现 `TunnelProvider` 接口，但不沿用“子进程存活即运行”的状态模型。Windows Tailscale CLI 只是系统后台服务的控制端：Provider 从显式路径、`PATH` 和标准安装目录发现 `tailscale.exe`，用 `tailscale status --json` 校验已登录状态并读取本机稳定的 `Self.DNSName`，再执行 `tailscale funnel --bg --yes http://127.0.0.1:<port>`。状态由 `tailscale funnel status --json` 查询，停止使用 `tailscale funnel --https=443 off`，不退出或卸载 Tailscale。

`TunnelService.start()` 是所有 Provider 和开机自启动共用的成功边界。它在 `provider.start()` 返回 URL 后调用注入的 `on_started(provider, url, port)` 回调。Web 层回调在守护线程中调用现有 `NotifierHub.send()`，通知失败只记录日志，不改变隧道启动结果。

## 通知

新增 `EventType.TUNNEL_STARTED` 及专用 Markdown 模板，载荷包含 `provider`、`provider_label`、`public_url`、`local_port` 和启动时间。所有当前启用且凭证有效的渠道都会收到通知，并继续遵循现有免打扰策略。钉钉从事件的 `action_url` / `action_title` 生成 ActionCard 单按钮，按钮文案为“立即打开闲鱼猎人”；其他事件仍保留原商品链接逻辑。

## 前端与错误处理

Provider 下拉框增加 Tailscale Funnel，并显示“需预先安装并登录”的说明和官方安装链接。通用二进制路径仍可覆盖自动发现。未安装、服务未运行、未登录、Funnel 未授权或 CLI 输出不可解析时，后端返回可操作的中文错误；不自动下载、不提权、不安装系统服务。

## 验证

后端测试覆盖 CLI 发现、登录预检、启动 URL、状态、停止、工厂注册、统一启动回调、通知模板和钉钉按钮。前端测试覆盖第三个 Provider 的元数据。最终运行相关 pytest、Vitest、TypeScript 构建、Python 编译和 diff 检查。

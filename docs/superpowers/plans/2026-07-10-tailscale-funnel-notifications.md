# Tailscale Funnel and Tunnel Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Tailscale Funnel as the third tunnel provider and notify every enabled notification channel with a clickable public URL after any provider starts.

**Architecture:** Implement Tailscale as a `TunnelProvider` backed by the installed Tailscale Windows service, then inject one post-start callback into `TunnelService` so Cloudflare, cpolar, Tailscale, manual starts, and auto-starts share the same notification path. Render a new domain event through the existing notifier templates and let DingTalk convert its action metadata into an ActionCard button.

**Tech Stack:** Python 3.14, FastAPI, subprocess, React 18, TypeScript, Ant Design, pytest, Vitest.

## Global Constraints

- Tailscale must be preinstalled and logged in; never auto-install or request elevation.
- Use `http://127.0.0.1:<port>` because Tailscale Funnel only supports the loopback proxy target.
- Notification failure must never make tunnel startup fail.
- Send through all currently enabled notifier channels and preserve quiet-hours behavior.
- Preserve all unrelated dirty-worktree changes.

---

### Task 1: Tailscale Provider

**Files:**
- Modify: `backend/xianyu_hunter/web/services/tunnel_providers.py`
- Test: `tests/test_tunnel_providers.py`

**Interfaces:**
- Produces: `TailscaleProvider(local_port: int, binary_path: str = "")`
- Produces: registry key `tailscale`

- [ ] **Step 1: Write failing provider tests**

Add tests asserting executable discovery, `tailscale status --json` preflight, `tailscale funnel --bg --yes http://127.0.0.1:8001`, stable `https://<Self.DNSName>`, `funnel status --json`, and `funnel --https=443 off`.

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_tunnel_providers.py -k tailscale`
Expected: FAIL because `TailscaleProvider` and registry entry do not exist.

- [ ] **Step 3: Implement the provider**

Implement discovery with `shutil.which("tailscale")` plus `%ProgramFiles%\\Tailscale\\tailscale.exe`; parse `BackendState == "Running"` and `Self.DNSName`; execute commands with hidden-window flags; override `status`, `start`, and `stop` because Funnel state belongs to the Tailscale service rather than a child process.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q tests/test_tunnel_providers.py`
Expected: all tunnel provider tests pass.

### Task 2: Unified Tunnel Start Notification

**Files:**
- Modify: `backend/xianyu_hunter/domain/events.py`
- Modify: `backend/xianyu_hunter/modules/notifier/templates.py`
- Modify: `backend/xianyu_hunter/modules/notifier/dingtalk.py`
- Modify: `backend/xianyu_hunter/web/services/tunnel_service.py`
- Modify: `backend/xianyu_hunter/web/routes/api_tunnel.py`
- Test: `tests/test_notifier.py`
- Test: `tests/test_notifier_new_channels.py`
- Create: `tests/test_tunnel_service.py`

**Interfaces:**
- Produces: `EventType.TUNNEL_STARTED`
- Produces: `TunnelService(on_started: Callable[[str, str, int], None] | None = None)`
- Consumes: `NotifierHub.send(Event(...))`

- [ ] **Step 1: Write failing notification tests**

Assert `TunnelService.start()` calls its callback once with provider name, URL, and resolved port; callback exceptions are isolated; template contains provider, URL, port and a Markdown link; DingTalk uses `action_url` and `action_title` for `singleURL` and `singleTitle`.

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_tunnel_service.py tests/test_notifier.py tests/test_notifier_new_channels.py -k "tunnel or action_url"`
Expected: FAIL because the event and callback do not exist.

- [ ] **Step 3: Implement event, template, and callback**

Add `TUNNEL_STARTED = "tunnel.started"` with `important` severity. Route it to a dedicated template. Extend DingTalk action selection without changing existing item-event behavior. In the API service factory, inject a callback that starts a daemon notification thread and calls `asyncio.run(get_container().notifier_hub.send(event))` with `action_url=public_url`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q tests/test_tunnel_service.py tests/test_notifier.py tests/test_notifier_new_channels.py`
Expected: all selected tests pass.

### Task 3: Configuration and Frontend

**Files:**
- Modify: `backend/xianyu_hunter/infra/yaml_config.py`
- Modify: `frontend/src/pages/Maintenance/Tunnel.tsx`
- Create: `frontend/src/pages/Maintenance/__tests__/tunnelProviders.test.ts`

**Interfaces:**
- Produces: provider metadata for `cloudflare`, `cpolar`, and `tailscale`
- Reuses: `TunnelConfig.binary_path` and `TunnelConfig.auto_start`

- [ ] **Step 1: Write failing frontend metadata test**

Move provider labels/descriptions into exported `TUNNEL_PROVIDERS` metadata and assert Tailscale has a label, fixed-domain description, install URL, and preinstall requirement.

- [ ] **Step 2: Verify RED**

Run: `npm exec vitest run src/pages/Maintenance/__tests__/tunnelProviders.test.ts` from `frontend`.
Expected: FAIL because Tailscale metadata is absent.

- [ ] **Step 3: Implement the UI**

Add the third Select option, Tailscale prerequisite alert and official install link, and a provider-specific binary-path placeholder. Update backend config documentation to include Tailscale.

- [ ] **Step 4: Verify GREEN**

Run: `npm exec vitest run src/pages/Maintenance/__tests__/tunnelProviders.test.ts` from `frontend`.
Expected: PASS.

### Task 4: Integration Verification and Reviews

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run backend verification**

Run: `pytest -q tests/test_tunnel_providers.py tests/test_tunnel_service.py tests/test_notifier.py tests/test_notifier_new_channels.py tests/test_dingtalk_notify_integration.py`
Expected: zero failures.

- [ ] **Step 2: Run frontend verification**

Run from `frontend`: `npm exec vitest run src/pages/Maintenance/__tests__/tunnelProviders.test.ts && npm run build`
Expected: tests and TypeScript/Vite build succeed.

- [ ] **Step 3: Run static checks**

Run: `python -m py_compile` for changed Python files and `git diff --check`.
Expected: exit code 0.

- [ ] **Step 4: Review backend and frontend changes**

Apply the repository-required backend and frontend review checklists, fix Blocker/Critical findings, and rerun affected tests.

- [ ] **Step 5: Run available SonarQube quality gate**

Use the repository SonarQube workflow when the configured service is available; report an unavailable service explicitly without fabricating a pass.

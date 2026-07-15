# SonarQube 扫描报告

**项目**: Xianyu Hunter (闲鱼自动捡漏与抢单系统)
**扫描日期**: 2026-07-12
**SonarQube 版本**: 26.1.0.118079 (Community Build)
**Scanner 版本**: sonar-scanner-cli 8.0.1.6346

---

## 1. 质量门禁状态

| 指标 | 状态 | 实际值 | 阈值 |
|------|------|--------|------|
| 新代码覆盖率 (new_coverage) | ERROR | 0.0% | >= 80% |
| 新代码重复密度 (new_duplicated_lines_density) | OK | 0.66% | <= 3% |
| 安全热点审查率 (new_security_hotspots_reviewed) | ERROR | 0.0% | = 100% |
| 新违规数 (new_violations) | OK | 0 | = 0 |

**整体质量门禁**: ERROR（覆盖率 0% + 安全热点未审查）

---

## 2. 代码度量

| 指标 | 值 |
|------|-----|
| 代码行数 (ncloc) | 74,312 |
| Bug 数 | 0 |
| 漏洞数 | 0 |
| 代码异味 (code_smells) | 0 |
| 安全热点 (security_hotspots) | 43 |
| 重复代码密度 | 0.9% |
| 覆盖率 | 0.0% |

---

## 3. OPEN 问题统计

| 状态 | 数量 |
|------|------|
| OPEN | 0 |
| CONFIRMED | 0 |
| CLOSED (历史) | 1,273+ |

**结论**: 当前无 OPEN 代码问题，所有历史问题已全部 CLOSED。

---

## 4. 测试结果

### 4.1 后端测试 (pytest)

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 通过 | 1,533 | 1,581 |
| 失败 | 48 | 0 |
| 警告 | 103 | 104 |
| 耗时 | 915s (15min) | 340s (5min40s) |

### 4.2 前端测试 (vitest)

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 通过 | 192 | 194 |
| 失败 | 2 | 0 |
| 测试文件 | 20 | 20 |

---

## 5. 测试修复汇总

### 5.1 后端修复 (48 个测试, 9 个文件)

| 文件 | 失败数 | 根因 | 修复方式 |
|------|--------|------|----------|
| test_buyer.py | 10 | FakeRepository 缺少 `get_task` 方法，`get_item` 签名未对齐 | 添加 `get_task` 方法 + `get_item` 增加 `user_id` 参数 |
| test_chatbot_escalation.py | 19 | 测试用 `asyncio.run()` 调用同步方法 `should_escalate` | 删除 `_run` 辅助函数，改为直接同步调用 |
| test_live_auto_buy.py | 9 | 测试用 `await` 调用同步函数 `_trigger_live_evaluation` | 去掉 9 处 `await` 关键字 |
| test_anticrawl_integration.py | 1 | `MtopSignedParams` 字段名 `appKey` → `app_key` (PEP 8) | 更正字段名 |
| test_api_anticrawl.py | 3 | `_m_h5_tk` mock 值 `"token_123"` 被判定为过期 | 改为动态时间戳格式 `32hex_{int(time.time()*1000)}` |
| test_browser_import_integration.py | 1 | `import_via_cdp` 签名增加 `request: Request` 参数 | 传入 `MagicMock()` 作为 request |
| test_cookie_layer_sync_fix.py | 2 | 硬编码 `_m_h5_tk` 时间戳已超过 TTL 1200s | 改为动态当前时间戳 |
| test_tunnel_providers.py | 3 | 源码 funnel 启动改用 `Popen` + 移除 `--https=443` | 更新 mock 为 `Popen` + 更新断言 |
| test_tunnel_service.py | 1 | fixture 未 mock `_ensure_provider` | 添加 `service._ensure_provider = lambda: provider` |

### 5.2 前端修复 (2 个测试, 1 个文件)

| 文件 | 失败数 | 根因 | 修复方式 |
|------|--------|------|----------|
| storage.test.ts | 2 | `_available` 模块级缓存导致测试间状态泄漏 | 导出 `__resetForTesting()` 函数，`beforeEach` 中调用 |

### 5.3 根因分类

| 根因类型 | 测试数 | 占比 |
|----------|--------|------|
| 测试未同步源码签名变更 | 21 | 42% |
| 测试误用 async/await 调用同步函数 | 28 | 56% |
| 测试 mock 数据格式错误 | 3 | 6% |

---

## 6. 安全热点状态

- 安全热点总数: 43
- 已审查率: 0.0%
- 状态: 需要在 SonarQube Web UI 中逐个审查并标记为 Safe/Acknowledged/Fixed

**注意**: 当前 SonarQube Token 缺少安全热点查询权限（`search_security_hotspots` 返回 "Insufficient privileges"），需提升 Token 权限或在 Web UI 中操作。

---

## 7. 修改的文件清单

### 测试文件 (10 个)
1. `tests/test_buyer.py` - FakeRepository 添加 get_task + get_item 签名对齐
2. `tests/test_chatbot_escalation.py` - 删除 _run 辅助函数，改为同步调用
3. `tests/test_live_auto_buy.py` - 去掉 9 处 await _trigger_live_evaluation
4. `tests/test_anticrawl_integration.py` - appKey → app_key
5. `tests/test_api_anticrawl.py` - _m_h5_tk 改为动态时间戳
6. `tests/test_browser_import_integration.py` - 添加 mock_request 参数
7. `tests/test_cookie_layer_sync_fix.py` - 硬编码时间戳改为动态
8. `tests/test_tunnel_providers.py` - Popen mock + 移除 --https=443
9. `tests/test_tunnel_service.py` - mock _ensure_provider
10. `frontend/src/utils/__tests__/storage.test.ts` - beforeEach 中重置模块缓存

### 源码文件 (2 个)
1. `frontend/src/utils/storage.ts` - 导出 `__resetForTesting()` 供测试重置模块级缓存
2. `frontend/package.json` - 添加 `"test": "vitest run"` 脚本

---

## 8. 后续建议

1. **覆盖率**: 当前 0%，需配置 pytest-cov 并在 sonar-project.properties 中添加覆盖率报告路径
2. **安全热点**: 43 个安全热点需在 SonarQube Web UI 中审查
3. **Token 权限**: 提升 SonarQube Token 权限以支持安全热点 API 查询
4. **CI 集成**: 建议将 SonarQube 扫描集成到 CI/CD 流水线中

---

*报告生成时间: 2026-07-12 02:15 (Asia/Hong_Kong)*
*扫描执行: sonar-scanner-cli 8.0.1.6346 + skipSystemTruststore=true*
*测试执行: pytest 9.1.1 (asyncio mode=auto) + vitest 4.1.9*

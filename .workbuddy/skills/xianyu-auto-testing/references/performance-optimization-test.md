# 性能优化回归测试参考文档

> 本文档为 xianyu-auto-testing 模式 R（性能优化回归测试模式）的详细操作参考。
> 所有参数从 `config.yaml#mode_r_performance_test` 读取，禁止硬编码。

## 1. SSE 流式响应验证

### 1.1 验证响应头

```powershell
# 从 config 读取 host/port/endpoint
$host = $config.web_process.host
$port = $config.web_process.port
$endpoint = $config.mode_r_performance_test.sse_test.endpoint_pattern -replace '\{task_id\}', $taskId
$url = "http://${host}:${port}${endpoint}"

# 验证 Content-Type 和 Transfer-Encoding
curl.exe -s -D - -o NUL -H "Authorization: Bearer $token" $url | Select-String "Content-Type|Transfer-Encoding"
```

**通过条件**：
- `Content-Type: text/event-stream; charset=utf-8`
- `Transfer-Encoding: chunked`

### 1.2 验证阶段事件序列

```powershell
# 捕获 SSE 事件流
$events = curl.exe -s -H "Authorization: Bearer $token" $url

# 按 config.expected_stages 顺序匹配
$expectedStages = $config.mode_r_performance_test.sse_test.expected_stages
foreach ($stage in $expectedStages) {
    if ($events -notmatch $stage) {
        Write-Warning "Missing stage: $stage"
    }
}
```

**通过条件**：所有 `expected_stages` 按顺序出现在事件流中。

### 1.3 验证前置检查

```powershell
# 请求不存在的 task_id
$invalidUrl = $url -replace '/\d+/', '/999999/'
$resp = curl.exe -s -o NUL -w "%{http_code}" -H "Authorization: Bearer $token" $invalidUrl

# 应返回 404 而非 SSE error 事件
if ($resp -eq "404") { Write-Output "PASS: precheck returns HTTP 404" }
else { Write-Warning "FAIL: expected 404, got $resp" }
```

## 2. 缓存命中验证

### 2.1 首次请求（触发完整搜索）

```powershell
$t1 = Measure-Command { $resp1 = curl.exe -s -H "Authorization: Bearer $token" $url }
Write-Output "First request: $($t1.TotalMilliseconds)ms"
```

**通过条件**：`$t1.TotalMilliseconds > operation_cost_threshold_ms`（默认 1000ms）

### 2.2 缓存命中请求

```powershell
$t2 = Measure-Command { $resp2 = curl.exe -s -H "Authorization: Bearer $token" $url }
Write-Output "Cache hit request: $($t2.TotalMilliseconds)ms"
```

**通过条件**：`$t2.TotalMilliseconds < hit_threshold_ms`（默认 10ms）

### 2.3 缓存命中率计算

```powershell
$sampleCount = $config.mode_r_performance_test.cache_test.sample_count
$hits = 0
for ($i = 0; $i -lt $sampleCount; $i++) {
    $t = Measure-Command { curl.exe -s -o NUL -H "Authorization: Bearer $token" $url }
    if ($t.TotalMilliseconds -lt $config.mode_r_performance_test.cache_test.hit_threshold_ms) {
        $hits++
    }
}
$rate = ($hits / $sampleCount) * 100
Write-Output "Cache hit rate: $rate%"
```

**通过条件**：`$rate >= 80%`

### 2.4 空结果策略验证

构造一个返回空结果的请求（如不存在的搜索关键词），验证：
1. 首次请求返回空列表
2. 立即重复请求仍触发实时查询（响应时间 > operation_cost_threshold_ms）

### 2.5 TTL 过期验证

等待 `ttl_seconds`（默认 60 秒）后请求，验证响应时间 > operation_cost_threshold_ms（重新触发搜索）。

## 3. SQL 层过滤验证

### 3.1 查询日志检查

```powershell
$dbLog = $config.mode_r_performance_test.sql_filter_test.db_log_file
$keywords = $config.mode_r_performance_test.sql_filter_test.expected_sql_keywords

foreach ($kw in $keywords) {
    if (Select-String -Path $dbLog -Pattern $kw -Quiet) {
        Write-Output "PASS: found $kw in DB log"
    } else {
        Write-Warning "FAIL: missing $kw in DB log"
    }
}
```

### 3.2 结果正确性验证

验证查询结果中的价格均在 `[price_min, price_max]` 区间内（容忍度 `price_tolerance`）。

## 4. list+count 合并查询验证

### 4.1 DB 查询计数

通过 DB 查询日志验证 list 和 count 在单次查询中完成（1 次 DB 往返，非 2 次）。

### 4.2 数据一致性验证

验证返回的 `total` 与分页数据一致（非末页时 `len(items) == page_size`）。

## 5. 优先级锁验证

### 5.1 high 优先级不被阻塞

1. 启动 low 优先级后台任务（如周期性搜索）
2. 立即发起 high 优先级请求（如实时查询）
3. 验证响应时间 < `high_max_wait_ms`（默认 5000ms）

### 5.2 low 优先级让出

通过日志验证 low 优先级任务检测到 high 等待后执行 `sleep` 让出：
```powershell
Select-String -Path $dbLog -Pattern "yield|让出|sleep.*priority"
```

## 6. 前端 useMemo 验证

通过 Chrome DevTools MCP 或 Playwright MCP 验证：

### 6.1 渲染计数

```javascript
// 通过 evaluate_script 注入
performance.mark('filter-start');
const filtered = items.filter(i => i.price >= minPrice);
performance.mark('filter-end');
performance.measure('filter', 'filter-start', 'filter-end');
```

验证多次渲染时 `filter` measure 只执行一次（useMemo 缓存）。

### 6.2 依赖项变更

修改过滤条件，验证 useMemo 重新计算（`filter` measure 再次执行）。

## 7. 性能对比报告模板

```markdown
## 性能优化回归测试报告

### 测试环境
- 服务地址: http://{host}:{port}
- 测试时间: {timestamp}
- 测试用例: {test_case_id}

### 测试结果

| 指标 | 优化前 | 优化后 | 提升倍数 | 状态 |
|------|--------|--------|----------|------|
| SSE 响应时间 | 4240ms | <10ms | 424x | PASS |
| 缓存命中率 | 0% | >80% | - | PASS |
| DB 查询往返次数 | 2 | 1 | 2x | PASS |
| SQL 过滤方式 | Python 全量 | SQL json_extract | - | PASS |
| 批量写入 IO | N 次 | 1 次 | Nx | PASS |
| 事件循环阻塞 | 同步阻塞 | run_in_executor | - | PASS |
| 优先级锁等待 | 15-20s | <5s | 3-4x | PASS |

### 结论
{all_pass | has_failures} - {summary}
```

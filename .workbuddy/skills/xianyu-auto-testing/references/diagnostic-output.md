# F. 诊断输出

> 对应决策节点：DT-07（需要让用户报告实际 UA 和判定结果）

## 检查项

### F1. 临时诊断日志（console.info）

读取 `config.yaml` 的 `diagnostic.console_prefix` 和 `mobile_detect` 段，在 `useMobileDetect.ts` 的 `detectMobile()` 函数中加临时日志：

```ts
function detectMobile(): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  const width = window.innerWidth
  const ontouchend = typeof document !== 'undefined' && '<touch_event_property>' in document
  const matchedByPattern = /<ua_pattern>/i.test(ua)
  const matchedByMac = /<macintosh_pattern>/i.test(ua) && ontouchend
  const result = matchedByPattern || matchedByMac || width <= <viewport_max_width>
  // 临时诊断日志：用于排查手机访问不跳转问题（确认根因后删除）
  console.info('<console_prefix>', {
    ua, width, ontouchend, matchedByPattern, matchedByMac, result,
  })
  return result
}
```

**为什么用 console.info 而非 console.log**：info 级别在浏览器 console 中默认显示，且可以通过级别过滤。

**适用场景**：用户能用 USB 连接电脑调试（iOS Safari 连 Mac Safari Web Inspector / Android Chrome 连 Chrome DevTools）。

### F2. 可见诊断浮层（visible diagnostic overlay）

**为什么需要可见浮层**：手机浏览器一般没有 console 入口，用户无法直接看 console 输出。可见浮层让用户在页面上直接看到判定依据。

读取 `config.yaml` 的 `diagnostic` 段，在 `App.tsx` 的 isMobile 检查之前插入：

```tsx
// 临时诊断模式：访问任意路径带 ?<query_param_name>=<query_param_value> 即显示判定依据
// 用于排查手机访问不跳转问题（确认根因后删除）
if (typeof window !== 'undefined'
  && new URLSearchParams(globalThis.location.search).get('<query_param_name>') === '<query_param_value>') {
  const ua = navigator.userAgent
  const width = window.innerWidth
  const ontouchend = '<touch_event_property>' in document
  return (
    <div style={{ padding: 20, fontFamily: 'monospace', fontSize: 13, wordBreak: 'break-all', whiteSpace: 'pre-wrap' }}>
      <h3>移动端判定诊断</h3>
      <div>isMobile: {String(isMobile)}</div>
      <div>pathname: {globalThis.location.pathname}</div>
      <div>innerWidth: {width}</div>
      <div>ontouchend in document: {String(ontouchend)}</div>
      <div>UA: {ua}</div>
      <hr />
      <div>判定逻辑：</div>
      <div>- UA 含 <ua_pattern>: {/<ua_pattern>/i.test(ua) ? '是' : '否'}</div>
      <div>- UA 含 <macintosh_pattern> + ontouchend: {/<macintosh_pattern>/i.test(ua) && ontouchend ? '是' : '否'}</div>
      <div>- innerWidth ≤ <viewport_max_width>: {width <= <viewport_max_width> ? '是' : '否'}</div>
      <div>预期跳转：{isMobile && !globalThis.location.pathname.startsWith('<basename><mobile_route_prefix>') ? '应跳转到 <mobile_route_prefix>' : '不跳转'}</div>
    </div>
  )
}
```

**字段说明**（来自 `diagnostic.visible_fields`）：
- `isMobile`：useMobileDetect 实际返回值
- `pathname`：当前浏览器路径
- `innerWidth`：视口宽度
- `ontouchend in document`：是否支持触摸事件
- `UA`：完整的 navigator.userAgent
- 判定逻辑（3 条分支命中情况）
- 预期跳转行为

### F3. 让用户访问诊断 URL

构建后，让用户在手机浏览器中访问：

```
https://<tunnel_url><basename>/?<query_param_name>=<query_param_value>
```

例如：`https://xxx.trycloudflare.com<basename>/?<query_param_name>=<query_param_value>`

用户报告诊断页面显示的内容，特别是：
- `isMobile` 值（true/false）
- `UA` 值（完整字符串）

### F4. 根据用户报告定位根因

| isMobile | UA 匹配 ua_pattern | UA 匹配 macintosh_pattern | ontouchend | innerWidth | 根因 |
|----------|----------------------|------------------|------------|------------|------|
| true | 是 | - | - | - | 正常，问题在其他地方 |
| false | 否 | 否 | - | > `<viewport_max_width>` | 用户用了桌面浏览器访问 |
| false | 否 | 是 | false | - | iPadOS 13+ 但 ontouchend 不可用 |
| false | 否 | 是 | true | - | useMobileDetect 逻辑有 bug |
| false | 否 | 否 | - | ≤ `<viewport_max_width>` | 视口兜底失效 |
| false | 是 | - | - | - | useMobileDetect 正则有 bug |

## 命中后动作

根据 F4 的根因表，执行对应修复：
- UA 不匹配 → 扩展 `mobile_detect.ua_pattern`
- ontouchend 不可用 → 改用 `navigator.maxTouchPoints > 0` 或 `window.matchMedia('(pointer: coarse)')`
- 视口兜底失效 → 检查 `viewport_max_width` 阈值
- useMobileDetect 逻辑 bug → 修复 Hook 实现

## 清理

根因定位并修复后，**删除临时诊断代码**：
- 移除 `useMobileDetect.ts` 中的 `console.info` 日志
- 移除 `App.tsx` 中的诊断浮层代码

## 输出报告

1. 用户报告的诊断页面内容
2. 根因表命中的行
3. 执行的修复
4. 清理后的代码状态

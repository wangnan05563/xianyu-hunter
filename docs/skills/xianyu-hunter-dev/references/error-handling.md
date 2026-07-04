# 前后端错误处理统一规范

> **来源**：从"抢单策略保存预览失败"问题中提炼
> **核心问题**：前端 catch 块只显示笼统的"预览失败"，用户无法定位后端具体错误

---

## 一、问题原型

**用户报告**：
> 在抢单策略页面把 `pass_score` 改成比 `auto_buy_score` 大的值，点击保存，提示"预览失败"，不知道哪里错了。

**根因**：
1. 后端 Pydantic `model_validator` 校验失败，返回 `HTTP 400`
2. 后端返回结构化错误：`{detail: {message: "配置校验失败", errors: [...]}}`
3. 前端 catch 块写 `catch { message.error('预览失败') }`，**丢弃所有错误细节**

---

## 二、统一规范

### 2.1 后端：错误响应格式

```python
from fastapi import HTTPException

# ✅ 结构化错误
raise HTTPException(
    status_code=400,
    detail={
        "message": "配置校验失败，未保存",
        "errors": err.errors()  # Pydantic 校验错误列表
    }
)

# ✅ 简单错误（字符串）
raise HTTPException(status_code=401, detail="认证已过期")
```

**exception_handler 统一处理**：

```python
# src/xianyu_hunter/web/middleware/exception_handler.py
@app.exception_handler(ValidationError)
async def handle_pydantic_validation(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": {"message": "参数校验失败", "errors": exc.errors()}}
    )
```

### 2.2 前端：错误解析工具

`frontend/src/utils/apiError.ts`：

```typescript
/**
 * 从 axios 错误中提取后端返回的可读错误信息。
 * 不在每个页面重复解析，统一在此提取人类可读信息。
 */
export function extractApiError(e: unknown): string {
  if (typeof e === 'object' && e !== null) {
    const resp = (e as { response?: { data?: unknown; status?: number } }).response
    if (resp) {
      const detail = (resp.data as Record<string, unknown>)?.detail

      // 简单字符串 detail
      if (typeof detail === 'string') return detail

      // 结构化 detail: { message, errors }
      if (typeof detail === 'object' && detail !== null) {
        const msg = (detail as Record<string, unknown>).message
        const errors = (detail as Record<string, unknown>).errors
        if (typeof msg === 'string') {
          if (Array.isArray(errors) && errors.length > 0) {
            return `${msg}：${errors.join('; ')}`
          }
          return msg
        }
      }

      if (resp.status === 401) return '认证已过期，请重新登录'
      if (resp.status === 500) return '服务器内部错误，请稍后重试'
    }
  }
  return e instanceof Error ? e.message : '操作失败'
}
```

### 2.3 前端：catch 块使用规范

```typescript
// ❌ 反例 1：笼统提示
try {
  await api.save()
} catch {
  message.error('保存失败')
}

// ❌ 反例 2：直接展示 e.message，可能不友好
try {
  await api.save()
} catch (e) {
  message.error((e as Error).message)
}

// ✅ 正例：统一提取
import { extractApiError } from '@/utils/apiError'

try {
  await api.save()
  message.success('保存成功')
} catch (e) {
  message.error(extractApiError(e), 5)  // 5 秒持续时间
}
```

---

## 三、错误信息格式要求

| 场景 | 持续时间 | 内容要求 |
|---|---|---|
| 操作成功 | 3 秒（默认） | 简洁动词 + 对象 |
| 操作失败 | **5 秒** | 包含后端 message + 校验 details |
| 警告 | 4 秒 | 解释影响 + 下一步建议 |

**为什么 5 秒**：错误信息通常较长（带校验细节），3 秒不够阅读。

---

## 四、各状态码对应的用户提示

| 状态码 | 用户提示 |
|---|---|
| 200 / 成功 | `message.success('操作成功')` |
| 400 校验失败 | `配置校验失败：[字段1] 错误1；[字段2] 错误2` |
| 401 认证过期 | `认证已过期，请重新登录` |
| 403 权限不足 | `权限不足` |
| 404 资源不存在 | `资源不存在` |
| 500 内部错误 | `服务器内部错误，请稍后重试` |
| 网络断开 | `网络连接失败，请检查网络` |

---

## 五、应用范围

**所有**涉及 API 调用的前端 catch 块都必须使用 `extractApiError`。包括但不限于：

- `pages/Config/BuyerStrategy.tsx`
- `pages/Config/EvalRules.tsx`
- `pages/Config/PriceStrategy.tsx`
- `pages/Config/SearchConfig.tsx`
- `pages/Config/NotifierChannels/index.tsx`
- `pages/Config/AIConfig/index.tsx`
- 任何后续新增的页面

**禁止**新增 `catch { message.error('xxx失败') }` 模式。

---

## 六、测试用例

### 后端（pytest）

```python
def test_save_invalid_score_should_return_400():
    """pass_score > auto_buy_score 应返回 400 with 结构化错误。"""
    cfg = get_config().model_dump()
    cfg["eval"]["pass_score"] = 90
    cfg["eval"]["auto_buy_score"] = 70

    response = client.post("/api/config/save", json={"payload": cfg, "dry_run": True})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
    assert "message" in body["detail"]
    assert "errors" in body["detail"]
    assert any("pass_score" in str(e) for e in body["detail"]["errors"])
```

### 前端（手动 E2E）

1. 打开 `/app/config/buyer`
2. 把 `pass_score` 改成比 `auto_buy_score` 大的值
3. 点击保存
4. 预期：message 显示"配置校验失败，未保存：通过分数 pass_score(90) 不能大于 自动抢单分数 auto_buy_score(70)"
5. 持续时间 ≥ 5 秒

---

## 七、检查清单

修改任何含 catch 块的代码后：

- [ ] 引入 `import { extractApiError } from '@/utils/apiError'`
- [ ] catch 块用 `extractApiError(e)` 替代字符串
- [ ] message 持续时间 ≥ 5 秒
- [ ] 错误信息包含后端返回的 message + errors
- [ ] 成功提示用 `message.success`
- [ ] 失败后业务状态正确（如 modal 不关闭）

---

## 八、相关文件

- `frontend/src/utils/apiError.ts` —— 错误提取工具
- `src/xianyu_hunter/web/middleware/exception_handler.py` —— 后端统一异常处理
- `src/xianyu_hunter/web/routes/api_config.py` —— 配置保存端点
- `frontend/src/pages/Config/*.tsx` —— 所有配置页面（必须改）

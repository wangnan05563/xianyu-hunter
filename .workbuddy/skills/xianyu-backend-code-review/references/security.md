# 后端安全审查（Security）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)

---

## 1. OWASP Top 10 覆盖

| 风险 | 规则编号 | 严重度 |
|---|---|---|
| A01 访问控制失效 | SC-04 / SC-05 | Critical |
| A02 加密失败 | SC-03 / SC-06 | Critical |
| A03 注入 | SC-01 / SC-02 | Critical |
| A04 不安全设计 | SC-10 | Suggestion |
| A05 安全配置错误 | SC-04 / SC-06 | Critical |
| A06 易受攻击组件 | （依赖审计） | Suggestion |
| A07 身份认证失败 | SC-04 | Critical |
| A08 数据完整性失败 | SC-10 | Suggestion |
| A09 日志记录失败 | SC-03 | Critical |
| A10 SSRF | SC-02 | Critical |

---

## 2. 注入防护

### 2.1 SQL 注入（SC-01）

```python
# ❌ 字符串拼 SQL
query = f"SELECT * FROM items WHERE seller_id = '{seller_id}'"

# ✅ 参数化
stmt = select(ItemORM).where(ItemORM.seller_id == seller_id)

# ✅ text() 也必须参数化
stmt = text("SELECT * FROM items WHERE seller_id = :sid")
await session.execute(stmt, {"sid": seller_id})
```

**ORM 是默认安全的**（参数化）；只在必须用 `text()` 时注意。

### 2.2 NoSQL 注入（如使用 MongoDB）

```python
# ❌ 直接传 dict
await db.items.find({"seller_id": user_input})

# ⚠️ 风险：user_input = {"$ne": null} 绕过
# ✅ 用类型校验
seller_id: str = validate_str(user_input)
await db.items.find({"seller_id": seller_id})
```

### 2.3 命令注入（SC-02）

```python
# ❌ shell 命令拼接
os.system(f"curl {user_url}")  # user_url = "; rm -rf /"

# ✅ 用 shlex 引用 + 不允许 shell
import shlex
args = ["curl", shlex.quote(user_url)]
subprocess.run(args, shell=False)

# ✅ 更好：避免 shell，用库
async with aiohttp.ClientSession() as session:
    async with session.get(user_url) as resp:
        return await resp.text()
```

### 2.4 路径穿越（SC-09）

```python
# ❌ 直接拼接
file_path = f"data/uploads/{user_filename}"

# ✅ 校验
from pathlib import Path
safe_name = Path(user_filename).name  # 去掉 ../
file_path = Path("data/uploads") / safe_name

# ✅ 验证解析后路径在允许目录内
base = Path("data/uploads").resolve()
target = (base / safe_name).resolve()
if not target.is_relative_to(base):
    raise HTTPException(400, detail="非法的文件路径")
```

---

## 3. 认证与授权（SC-04）

### 3.1 所有 API 端点必须认证

```python
# ✅ 认证依赖
from xianyu_hunter.web.middleware.auth import get_current_user

@router.post("/api/items")
async def create_item(
    item: ItemCreate,
    user: User = Depends(get_current_user)  # ✅ 必填
):
    ...

# ❌ 漏认证
@router.post("/api/items")
async def create_item(item: ItemCreate):
    ...  # 任何人都能调用
```

### 3.2 角色 / 权限检查

```python
# ✅ 细粒度权限
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, detail="权限不足")
    await user_repo.delete(user_id)
```

### 3.3 资源所有权

```python
# ✅ 用户只能改自己的数据
async def update_task(
    task_id: str,
    update: TaskUpdate,
    user: User = Depends(get_current_user)
):
    task = await task_repo.get_by_id(task_id)
    if task.owner_id != user.id:
        raise HTTPException(403, detail="无权限")
    await task_repo.update(task_id, update)
```

---

## 4. 敏感数据保护（SC-03 / SC-05）

### 4.1 凭据管理

```python
# ❌ 硬编码
WEBHOOK_TOKEN = "sk-1234567890abcdef"

# ✅ 环境变量 / keyring
import os
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN")
if not WEBHOOK_TOKEN:
    raise ConfigError("WEBHOOK_TOKEN 未设置")

# ✅ 高敏感：keyring
import keyring
PASSWORD = keyring.get_password("xianyu", "cookie")
```

### 4.2 日志脱敏

```python
# ❌ 打印敏感信息
logger.info(f"用户登录: cookie={cookie}")
print(f"token: {token}")

# ✅ 脱敏日志
def mask(s: str, n: int = 4) -> str:
    if not s:
        return ""
    return f"{s[:n]}***{s[-n:]}" if len(s) > n * 2 else "***"

logger.info(f"用户登录: cookie={mask(cookie)}")
```

### 4.3 API 响应脱敏

```python
# web/routes/api_config.py
_REDACT_KEYS = frozenset({
    "serverchan_key", "pushplus_token",
    "bark_key", "bark_server",
    "cookie", "cookies", "session_id"
})

def _redact(d: dict) -> dict:
    for k in list(d.keys()):
        if k in _REDACT_KEYS and isinstance(d[k], str) and d[k]:
            d[k] = "***"
        elif isinstance(d[k], dict):
            _redact(d[k])
    return d

@router.get("/api/config")
async def get_config():
    cfg = get_config().model_dump()
    return _redact(cfg)
```

### 4.4 数据库存储

```python
# ⚠️ 敏感字段加密
# 用 cryptography.fernet 加密 cookie
from cryptography.fernet import Fernet

def encrypt_cookie(cookie: str) -> str:
    f = Fernet(get_encryption_key())
    return f.encrypt(cookie.encode()).decode()

def decrypt_cookie(encrypted: str) -> str:
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted.encode()).decode()
```

---

## 5. 错误处理安全（SC-06）

### 5.1 不暴露内部细节

```python
# ❌ 反例：暴露堆栈 / 路径
raise HTTPException(500, detail=str(e))
# "FileNotFoundError: data/config.yaml"

# ✅ 正确：脱敏后返回
try:
    config = load_config()
except FileNotFoundError as e:
    logger.exception("配置加载失败")  # 详细日志留在服务端
    raise HTTPException(500, detail="配置加载失败")
```

### 5.2 统一异常处理

```python
# web/middleware/exception_handler.py
@app.exception_handler(Exception)
async def handle_unexpected(request, exc):
    logger.exception(f"未处理异常: {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务器错误"}  # 不暴露细节
    )
```

### 5.3 校验错误信息

```python
# Pydantic 校验错误可能暴露内部字段名
# ✅ 自定义错误信息
@field_validator('cookie', mode='before')
def validate_cookie(cls, v):
    if not v:
        return v
    if len(v) > 4096:
        raise ValueError("Cookie 长度超过限制")  # 不暴露具体长度
    return v
```

---

## 6. 外部 API 响应校验（SC-08）

### 6.1 不信任外部响应

```python
# ❌ 直接用响应
async def fetch_user_data(user_id: str):
    data = await external_api.get(f"/users/{user_id}")
    return data["email"]  # 外部响应格式可能变

# ✅ 校验后用 Pydantic
class ExternalUser(BaseModel):
    id: str
    email: EmailStr
    name: str

async def fetch_user_data(user_id: str) -> ExternalUser:
    raw = await external_api.get(f"/users/{user_id}")
    return ExternalUser.model_validate(raw)  # 校验失败抛 ValidationError
```

### 6.2 大小限制

```python
# 防止恶意大响应
async def fetch_data():
    async with session.get(url) as resp:
        if resp.content_length and resp.content_length > 10_000_000:
            raise ValueError("响应过大")
        return await resp.json()
```

---

## 7. CSRF

### 7.1 SameSite Cookie

```python
# 后端 Set-Cookie
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,
    secure=True,
    samesite="strict"  # 防止 CSRF
)
```

### 7.2 CSRF Token（传统方案）

```python
@router.post("/api/transfer")
async def transfer(
    amount: float,
    csrf_token: str = Header(...)
):
    if not validate_csrf(csrf_token, current_user):
        raise HTTPException(403, detail="CSRF token 错误")
    ...
```

---

## 8. 安全审计 checklist

| 类别 | 检查项 |
|---|---|
| SQL 注入 | 无字符串拼 SQL？参数化？ |
| 命令注入 | shell=False？shlex 引用？ |
| 路径穿越 | Path 安全？resolve 验证？ |
| 认证 | 所有端点有 Depends(get_current_user)？ |
| 授权 | 资源所有权校验？角色检查？ |
| 凭据 | 硬编码？环境变量？keyring？ |
| 日志 | 脱敏？敏感信息不打印？ |
| API 响应 | 敏感字段 redact？ |
| 错误 | 不暴露内部细节？统一处理？ |
| 外部响应 | Pydantic 校验？大小限制？ |
| CSRF | SameSite？Token？ |
| 依赖 | `pip audit` 无高危？ |

---

## 9. 常见反模式

| 反模式 | 风险 | 修复 |
|---|---|---|
| `os.system(f"cmd {input}")` | 命令注入 | subprocess + shell=False + shlex |
| `f"SELECT ... WHERE x = '{input}'"` | SQL 注入 | 参数化 / ORM |
| `open(f"data/{input}")` | 路径穿越 | Path 校验 |
| `print(f"token={token}")` | 泄露 | 脱敏 / 删除 |
| `return config.model_dump()` | 返回 cookie | `_redact` 脱敏 |
| 路由漏认证 | 越权 | `Depends(get_current_user)` |
| 外部响应直接用 | 解析失败 / 注入 | Pydantic 校验 |
| `except: pass` | 错误信息丢 | 记录 + 上抛 |
| 错误返回堆栈 | 泄露内部 | 统一处理 + 脱敏 |

---

## 10. 安全工具集成

```bash
# 依赖漏洞扫描
pip install pip-audit
pip-audit

# 代码安全扫描
pip install bandit
bandit -r src/xianyu_hunter/

# SAST 工具
# SonarQube / Snyk / CodeQL
```

### 10.1 Bandit 配置

```toml
# pyproject.toml
[tool.bandit]
exclude_dirs = ["tests", "data"]
tests = ["B201", "B301", "B302", "B303", "B304", "B305"]
```

### 10.2 Pre-commit Hook

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/PyCQA/bandit
  rev: 1.7.5
  hooks:
    - id: bandit
      args: ['-c', 'pyproject.toml']
      additional_dependencies: ['bandit[toml]']
```

---

## 11. 复盘：从对话中提炼

### 11.1 案例：API 响应含敏感信息（已修复）

`api_config.py` 修复前可能直接返回 `get_config().model_dump()`，**包含 cookie 等敏感字段**。

**修复**：用 `_REDACT_KEYS` 递归脱敏。

**审查意义**：每个返回用户配置的端点必须脱敏，不仅是 `api_config`。

### 11.2 案例：错误信息不友好（间接安全风险）

保存失败只显示"预览失败"，**用户无法判断是认证过期还是配置错误**。

**安全风险**：如果用户不知道是认证过期，可能尝试其他操作（误操作风险）。

**修复**：`extractApiError` 区分 401 / 400 / 500，提示明确。

---

## 12. 参考

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Bandit 文档](https://bandit.readthedocs.io/)
- [Pydantic 安全模式](https://docs.pydantic.dev/latest/concepts/security/)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)

---

## 十一、数据库管理 API 安全

### 11.1 SQL 注入防护

| 防护层 | 实现 | 说明 |
|---|---|---|
| 表名 | 白名单校验 `_validate_table()` | 仅允许 `ALLOWED_TABLES` 中的表 |
| 列名/标识符 | 正则校验 `_validate_identifier()` | 仅允许 `[a-zA-Z_][a-zA-Z0-9_]*` |
| 值 | 参数化绑定 `:param` | 永远不拼接用户输入到 SQL |

**铁律**：用户输入**绝不**拼接到 SQL 标识符位置（表名/列名/ORDER BY），只通过白名单或正则校验。

### 11.2 二次确认机制

危险操作（删除/批量删除/导入）必须传入 `confirm_token`：

```python
CONFIRM_TOKEN = "CONFIRM_DELETE"

@router.delete("/tables/{table}/rows/{pk_value:path}")
def delete_row(table: str, pk_value: str, confirm_token: str = Query(...)):
    if confirm_token != CONFIRM_TOKEN:
        raise HTTPException(status_code=400, detail=f"需要 confirm_token={CONFIRM_TOKEN}")
```

### 11.3 操作限制

| 限制 | 值 | 说明 |
|---|---|---|
| 单页最大行数 | `MAX_PAGE_SIZE = 1000` | 防止一次查询过多数据 |
| 批量删除上限 | 1000 行/次 | 防止误操作大量数据 |
| 导入上限 | 5000 行/次 | 防止大数据量导入超时 |
| 确认 token | `CONFIRM_DELETE` | 前端需手动输入确认词 |

### 11.4 审计日志

所有 DML 操作写入 events 表，可追溯：

- 操作类型（`db_admin.create` / `db_admin.delete` / ...）
- 操作表名 + 主键值
- 级联影响详情（受影响表+行数）
- 操作时间 + 日志级别

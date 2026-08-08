# 字符编码与 I/O 边界规范（Encoding & I/O）

> **版本**：v1.0
> **来源**：从 FAQ 乱码问题复盘中提炼
> **适用范围**：`src/xianyu_hunter/`（Python）+ `frontend/src/`（TypeScript）+ 外部脚本调用 HTTP API 的场景
> **配套技能**：`xianyu-hunter-dev`（编码规范）、`xianyu-frontend-code-review` / `xianyu-backend-code-review`（审查要点）

---

## 一、复盘来源与适用场景

### 1.1 复盘案例概述

数据库存储文本字段出现 ASCII `0x3f`（`?`）字符，前端展示为问号。经原始字节诊断、链路排查、审计日志追溯，定位为外部脚本通过 PowerShell 默认 `cp936/gbk` 编码 HTTP body，中文字符在传输前已被替换为 `?`。

### 1.2 适用场景

- 所有"存储文本字段的表"（含 FAQ / 配置 / 名称 / 描述等业务文本字段）
- 通过外部脚本（PowerShell / cmd / curl / Python `requests`）调用本项目 HTTP API 的场景
- 跨进程 / 跨语言 / 跨终端的 I/O 边界（数据库 ↔ 后端 ↔ HTTP ↔ 前端 ↔ 外部脚本）
- 调试字符乱码类问题时（避免被 stdout 编码误导）

### 1.3 不适用场景

- 纯内部 Python 函数调用（无 I/O 边界，编码由解释器保证）
- ORM 完整类型转换路径（`session.query(Model)` 自动处理 datetime / json）
- 浏览器渲染层字体缺失导致的"方框 /豆腐块"（非编码问题）

---

## 二、字符编码铁律

### 2.1 通用原则

| # | 原则 | 落地手段 |
|---|---|---|
| ENC-01 | **存储层统一 UTF-8** | SQLite 默认 UTF-8，**禁止**显式设置 `PRAGMA encoding` 为其他值；MySQL/PG 连接串必须带 `charset=utf8mb4` |
| ENC-02 | **HTTP 响应显式声明 charset** | `Content-Type: application/json; charset=utf-8`（FastAPI 默认满足，自定义响应需手动加） |
| ENC-03 | **写文件显式 encoding** | `Path("x").write_text(s, encoding="utf-8")` / `open(..., encoding="utf-8")`；**禁止**依赖系统默认 |
| ENC-04 | **读文件显式 encoding** | 同上；处理未知编码用 `chardet` / `charset-normalizer` 检测后再解码 |
| ENC-05 | **跨边界传递用 bytes 诊断** | 出现乱码时先用原始字节读取，绕过 stdout 编码干扰 |
| ENC-06 | **外部脚本调用 API 必须显式声明编码** | PowerShell / cmd / curl / Python `requests` 均需显式设置 `Content-Type` 与 body 编码 |
| ENC-07 | **不依赖终端默认编码** | Windows PowerShell 默认 `cp936/gbk`，Linux/macOS 终端默认 UTF-8；任何依赖系统编码的代码都视为 Bug |
| ENC-08 | **JSON 序列化禁止 ensure_ascii=False 之外的隐式转换** | `json.dumps(obj, ensure_ascii=False)` 输出真实字符；默认 `ensure_ascii=True` 输出 `\uXXXX` 转义也可接受 |

### 2.2 后端 Python 编码规范

```python
# ✅ 正确：所有文件 I/O 显式 encoding
from pathlib import Path
content = Path("data/faq.json").read_text(encoding="utf-8")
Path("data/faq.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ✅ 正确：HTTP 响应显式 charset
from fastapi import Response
return Response(content=json.dumps(data, ensure_ascii=False), media_type="application/json; charset=utf-8")

# ✅ 正确：sqlite3 连接读取原始字节诊断乱码
import sqlite3
conn = sqlite3.connect("data/xianyu.db")
conn.text_factory = bytes  # 绕过默认 text_factory，直接读 bytes
rows = conn.execute("SELECT question FROM chatbot_faqs").fetchall()
for r in rows:
    print([hex(b) for b in r[0]])  # 看到真实字节，不被 stdout 编码干扰

# ❌ 错误：依赖系统默认编码
content = open("data/faq.json").read()  # Windows 上可能是 cp936

# ❌ 错误：用 print 直接诊断乱码
print(repr(value))  # stdout 自身编码会再次编码，看不到真实字节
```

### 2.3 前端 TypeScript 编码规范

```typescript
// ✅ fetch / axios 默认按 UTF-8 解码响应 body，无需额外设置
// 但自定义 Response 时需显式声明
const resp = new Response(JSON.stringify(data), {
  headers: { 'Content-Type': 'application/json; charset=utf-8' }
})

// ✅ 处理二进制响应（如文件下载）用 arrayBuffer + TextDecoder
const buf = await resp.arrayBuffer()
const text = new TextDecoder('utf-8').decode(buf)

// ❌ 错误：假设响应是 latin-1 或其他编码
const text = await resp.text()  // 默认 UTF-8，但若后端误返回其他编码会乱码
```

### 2.4 外部脚本调用 HTTP API 规范

#### PowerShell

```powershell
# ✅ 正确：显式 UTF-8 body + Content-Type
$body = @{ question = "如何退款"; answer = "请联系客服" } | ConvertTo-Json -Depth 10
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
Invoke-RestMethod -Uri "http://localhost:8000/api/chatbot/faq" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body $bytes

# ❌ 错误：直接传字符串（PowerShell 默认 cp936 编码 body）
Invoke-RestMethod -Uri "..." -Method Post -Body $body  # 中文被替换为 ?
```

#### cmd + curl

```bat
# ✅ 正确：curl 的 --data-binary 接受 UTF-8 文件
curl -X POST http://localhost:8000/api/chatbot/faq ^
  -H "Content-Type: application/json; charset=utf-8" ^
  --data-binary @payload.json

# ❌ 错误：用 -d "..." 直接传中文（cmd 默认 gbk）
```

#### Python `requests`

```python
# ✅ 正确：requests 默认 UTF-8 编码 body
import requests
payload = {"question": "如何退款", "answer": "请联系客服"}
requests.post("http://localhost:8000/api/chatbot/faq", json=payload)

# ❌ 错误：手动 data=json.dumps(payload) 不指定 Content-Type
requests.post(url, data=json.dumps(payload))  # 可能被默认 latin-1 编码
```

---

## 三、I/O 边界排查方法论

### 3.1 字符乱码诊断五步法

> **复盘提炼**：FAQ 乱码问题的完整诊断流程

```
Step 1: 现象定位
  ↓ - UI 显示问号 → 是字符 0x3f 还是字体缺失？
Step 2: 字节层诊断（绕过 stdout）
  ↓ - 用 conn.text_factory = bytes 读原始字节
  ↓ - 确认存储的就是 0x3f（非显示编码问题）
Step 3: 编码链路逐层排查
  ↓ - 存储层：PRAGMA encoding（SQLite 默认 UTF-8）
  ↓ - ORM 层：SQLAlchemy 是否设置 charset
  ↓ - API 层：序列化时是否 ensure_ascii=False
  ↓ - HTTP 层：Content-Type 是否带 charset
  ↓ - 客户端层：终端 / 浏览器默认编码
Step 4: 写入源追溯
  ↓ - 审计日志：source / ip / user-agent / 时间戳
  ↓ - 时间间隔：批量写入（毫秒级间隔）→ 脚本调用
  ↓ - 调用方式：PowerShell / curl / Python requests
Step 5: 根因定位
  → - 外部脚本默认编码与 API 期望不一致
```

### 3.2 编码链路排查清单

| 层 | 检查项 | 默认值 | 验证方法 |
|---|---|---|---|
| 数据库存储 | SQLite `PRAGMA encoding` | UTF-8 | `PRAGMA encoding;` |
| 数据库连接 | SQLAlchemy `connect_args` | UTF-8 | `engine.url.query` |
| ORM 序列化 | Pydantic `model_dump()` | Unicode | `repr(obj.field)` |
| HTTP 响应 | `Content-Type` 头 | `application/json` | `curl -i` 查看响应头 |
| HTTP 响应 body | `json.dumps(ensure_ascii=?)` | `True`（转义） | `curl -d ... \| xxd \| head` |
| 客户端接收 | 浏览器 / curl 解码 | UTF-8 | 浏览器 DevTools Network |
| 终端 stdout | PowerShell / cmd 编码 | cp936/gbk | `chcp` 命令查看 |
| 外部脚本 body 编码 | PowerShell `Invoke-RestMethod -Body` | cp936 字符串 | 显式 `[Encoding]::UTF8.GetBytes()` |

### 3.3 写入源追溯方法

> **复盘提炼**：通过审计日志 + 时间戳推断外部脚本调用

```python
# 审计日志关键字段
{
    "source": "web",          # 来源（web / api / script）
    "ip": "127.0.0.1",        # 调用方 IP
    "user_agent": "python-requests/2.31.0",  # UA
    "created_at": "2026-07-04T10:00:00.123",  # 毫秒级时间戳
    "action": "create",       # 操作类型
    "entity_type": "faq",     # 实体类型
    "entity_id": 1            # 实体 ID
}
```

**判断逻辑**：
1. **时间间隔 < 1 秒** 的批量写入 → 高度怀疑脚本调用
2. **`source=web`** + **无浏览器 UA** → 脚本模拟前端调用
3. **`127.0.0.1`** → 本地脚本调用
4. **写入内容包含 `0x3f`** → 编码在写入前已损坏

### 3.4 调试脚本注意事项

| 注意点 | 错误做法 | 正确做法 |
|---|---|---|
| 读取数据库 | `print(repr(value))` | `conn.text_factory = bytes` + 打印 codepoints |
| 写入 stdout | `print(value)` | `sys.stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` 后再 print |
| 终端编码 | 信任 `print` 输出 | `chcp`（Windows）/ `locale`（Linux）查终端编码 |
| 临时脚本 | 留在仓库 | 用完即删，禁止提交 `_debug_*.py` |

---

## 四、配置管理

### 4.1 编码相关配置项

> **原则**：所有编码相关参数通过配置文件管理，禁止硬编码

```python
# config/config.example.yaml
encoding:
  database: "utf-8"           # 数据库连接编码
  file_io: "utf-8"            # 文件读写编码
  http_response: "utf-8"      # HTTP 响应编码
  log_output: "utf-8"         # 日志输出编码
```

```python
# src/xianyu_hunter/infra/yaml_config.py
class EncodingConfig(BaseModel):
    database: str = "utf-8"
    file_io: str = "utf-8"
    http_response: str = "utf-8"
    log_output: str = "utf-8"

    @field_validator("*")
    @classmethod
    def validate_encoding(cls, v: str) -> str:
        allowed = {"utf-8", "utf-8-sig", "gbk", "gb2312", "cp936"}
        if v.lower() not in allowed:
            raise ValueError(f"不支持的编码: {v}, 允许: {allowed}")
        return v.lower()
```

### 4.2 外部脚本模板

> **原则**：项目提供标准化的外部脚本调用模板，避免编码踩坑

```python
# scripts/templates/call_api.py
"""调用本项目 HTTP API 的标准模板。"""
import json
import requests
from pathlib import Path

def call_api(url: str, payload: dict) -> dict:
    """显式 UTF-8 编码 body，避免终端默认编码干扰。"""
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    # 用 json= 参数让 requests 自动 UTF-8 编码
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    payload = json.loads(Path("payload.json").read_text(encoding="utf-8"))
    result = call_api("http://localhost:8000/api/chatbot/faq", payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

```powershell
# scripts/templates/call_api.ps1
# 调用本项目 HTTP API 的标准模板
$ErrorActionPreference = "Stop"

$body = Get-Content -Path "payload.json" -Raw -Encoding UTF8
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/chatbot/faq" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body $bytes

$response | ConvertTo-Json -Depth 10
```

---

## 五、测试规范

### 5.1 编码回归测试

```python
# tests/test_encoding.py
import sqlite3
import json
from pathlib import Path

def test_sqlite_default_encoding_is_utf8(tmp_path):
    """SQLite 默认 encoding 必须为 UTF-8。"""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    encoding = conn.execute("PRAGMA encoding").fetchone()[0]
    assert encoding == "UTF-8"

def test_text_field_preserves_chinese(tmp_path):
    """存储文本字段必须保留中文字符（不变成 0x3f）。"""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (content TEXT)")
    conn.execute("INSERT INTO t VALUES (?)", ("如何退款",))
    conn.commit()

    # 用 bytes 模式读取，绕过 stdout 编码
    conn.text_factory = bytes
    row = conn.execute("SELECT content FROM t").fetchone()
    assert b"?" not in row[0], "存储内容包含 0x3f，编码已损坏"
    assert row[0].decode("utf-8") == "如何退款"

def test_http_api_preserves_chinese(test_client):
    """HTTP API 写入的中文字符必须正确存储。"""
    payload = {"question": "如何退款", "answer": "请联系客服"}
    resp = test_client.post("/api/chatbot/faq", json=payload)
    assert resp.status_code == 200

    # 验证存储内容（非 API 返回）
    conn = sqlite3.connect("data/xianyu.db")
    conn.text_factory = bytes
    row = conn.execute("SELECT question FROM chatbot_faqs ORDER BY id DESC LIMIT 1").fetchone()
    assert b"?" not in row[0], "API 写入的中文字符被替换为 0x3f"
```

### 5.2 外部脚本调用回归

```python
def test_powershell_script_writes_utf8(tmp_path):
    """PowerShell 脚本调用 API 必须用 UTF-8 body。"""
    script = Path("scripts/templates/call_api.ps1").read_text(encoding="utf-8")
    assert "[System.Text.Encoding]::UTF8.GetBytes" in script, "脚本必须显式 UTF-8 编码 body"
    assert "charset=utf-8" in script, "脚本必须显式声明 Content-Type charset"
```

---

## 六、Anti-Pattern（反模式）

| # | 反模式 | 风险 | 修复 |
|---|---|---|---|
| AP-01 | `open(file)` 不带 encoding | Windows 上用 cp936，跨平台行为不一致 | `open(file, encoding="utf-8")` |
| AP-02 | `print(repr(value))` 诊断乱码 | stdout 编码再次编码，看不到真实字节 | `conn.text_factory = bytes` + 打印 codepoints |
| AP-03 | PowerShell `Invoke-RestMethod -Body $str` | 默认 cp936 编码 body，中文变 `?` | `[Encoding]::UTF8.GetBytes($str)` |
| AP-04 | curl `-d "中文"` | cmd 默认 gbk 编码 body | `--data-binary @payload.json` + UTF-8 文件 |
| AP-05 | `requests.post(url, data=json.dumps(payload))` | 可能被默认 latin-1 编码 | `requests.post(url, json=payload)` |
| AP-06 | 数据库存储 `0x3f` 后才排查 | 已损坏数据无法恢复 | 写入前在 API 层校验非 ASCII 字符不为 `?` |
| AP-07 | 临时调试脚本留在仓库 | 污染 git history | 用完即删，禁止提交 `_debug_*.py` |
| AP-08 | 信任 `print` 输出判断编码 | 终端编码可能再次编码 | 用字节级工具（xxd / hexdump）验证 |

---

## 七、参考

- [PEP 393 - Flexible String Representation](https://peps.python.org/pep-0393/)
- [SQLite Text Encoding](https://www.sqlite.org/pragma.html#pragma_encoding)
- [PowerShell Encoding 指南](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)
- [项目编码规范总入口](coding-standards.md)
- [错误处理规范](error-handling.md)

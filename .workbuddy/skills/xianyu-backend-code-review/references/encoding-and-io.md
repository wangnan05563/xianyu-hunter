# 后端编码与 I/O 审查（Encoding & I/O）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **重点**：字符编码 / 文件 I/O / HTTP 响应 / 外部脚本调用 API 的后端审查要点
> **复盘来源**：FAQ 乱码问题（数据库存储 ASCII 0x3f）

---

## 1. 审查维度（ENC-*）

### 1.1 文件 I/O 编码（ENC-01）

| 规则 | 严重度 |
|---|---|
| **所有 `open()` / `Path.read_text()` / `Path.write_text()` 必须显式 `encoding="utf-8"`** | Critical |
| **禁止依赖系统默认编码**（Windows cp936 / Linux UTF-8 不一致） | Critical |
| **处理未知编码文件必须用 `chardet` / `charset-normalizer` 检测** | Suggestion |
| **写 JSON 文件用 `ensure_ascii=False` 保留真实字符** | Suggestion |

```python
# ❌ Critical 违反 ENC-01：依赖系统默认编码
content = open("data/faq.json").read()
Path("data/faq.json").write_text(json.dumps(data))

# ✅ 正确：显式 UTF-8
content = Path("data/faq.json").read_text(encoding="utf-8")
Path("data/faq.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
```

### 1.2 数据库编码（ENC-02）

| 规则 | 严重度 |
|---|---|
| **SQLite 不显式设置 `PRAGMA encoding`**（默认 UTF-8） | Critical |
| **MySQL/PG 连接串必须带 `charset=utf8mb4`** | Critical |
| **存储文本字段禁止包含 ASCII `0x3f`（`?`）作为中文字符** | Critical |
| **写入前在 API 层校验非 ASCII 字符不为 `?`** | Suggestion |

```python
# ❌ Critical 违反 ENC-02：显式设置非 UTF-8 编码
conn.execute("PRAGMA encoding = 'GBK'")  # 破坏默认 UTF-8

# ❌ Critical 违反 ENC-02：MySQL 连接未指定 charset
engine = create_engine("mysql://user:pass@host/db")  # 默认 latin-1

# ✅ 正确：MySQL 显式 utf8mb4
engine = create_engine("mysql://user:pass@host/db?charset=utf8mb4")
```

### 1.3 HTTP 响应编码（ENC-03）

| 规则 | 严重度 |
|---|---|
| **HTTP 响应 `Content-Type` 必须带 `charset=utf-8`** | Suggestion |
| **JSON 响应默认 `ensure_ascii=True`（转义）或 `False`（真实字符）二选一，明确标注** | Suggestion |
| **自定义 `Response` 必须显式 `media_type="application/json; charset=utf-8"`** | Suggestion |

```python
# ❌ 违反 ENC-03：自定义响应未声明 charset
from fastapi import Response
return Response(content=json.dumps(data), media_type="application/json")

# ✅ 正确：显式 charset
return Response(
    content=json.dumps(data, ensure_ascii=False),
    media_type="application/json; charset=utf-8"
)
```

### 1.4 外部 API 输入校验（ENC-04）

| 规则 | 严重度 |
|---|---|
| **写入文本字段前校验：非 ASCII 字符不为 `?`（0x3f）** | Critical |
| **校验失败返回 400 + 明确错误信息** | Critical |
| **审计日志记录 source / UA / IP / 毫秒级时间戳** | Suggestion |

```python
# ✅ 正确：写入前校验中文不为 ?
from pydantic import field_validator

class FAQCreate(BaseModel):
    question: str
    answer: str

    @field_validator("question", "answer")
    @classmethod
    def validate_no_mojibake(cls, v: str) -> str:
        """检测中文字符被替换为 ? 的乱码输入。"""
        if "?" in v and any(ord(c) > 127 for c in v):
            raise ValueError("输入包含乱码字符 '?'，可能编码不一致")
        return v
```

### 1.5 调试脚本管理（ENC-05）

| 规则 | 严重度 |
|---|---|
| **临时调试脚本（`_debug_*.py`）必须用完即删，禁止提交** | Critical |
| **调试脚本必须显式 UTF-8 编码 stdout** | Suggestion |
| **数据库乱码诊断必须用 `conn.text_factory = bytes` 绕过 stdout 编码** | Suggestion |

```python
# ✅ 正确：调试脚本标准模式
import sys
import io
import sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

conn = sqlite3.connect("data/xianyu.db")
conn.text_factory = bytes  # 绕过 stdout 编码，读原始字节
rows = conn.execute("SELECT question FROM chatbot_faqs").fetchall()
for r in rows:
    print([hex(b) for b in r[0]])  # 看到真实字节
```

### 1.6 配置管理（ENC-06）

| 规则 | 严重度 |
|---|---|
| **编码相关参数（database / file_io / http_response / log_output）通过 YAML 配置管理** | Suggestion |
| **禁止在代码中硬编码编码字符串**（如 `"utf-8"` 散落在多处） | Suggestion |
| **配置加载用 Pydantic `EncodingConfig` 模型校验** | Suggestion |

```python
# ❌ 违反 ENC-06：硬编码编码字符串
content = Path("data/x.json").read_text(encoding="utf-8")
Path("data/y.json").write_text(s, encoding="utf-8")
# 散落多处，无法统一修改

# ✅ 正确：从配置读取
from xianyu_hunter.infra.yaml_config import get_config
cfg = get_config().encoding
content = Path("data/x.json").read_text(encoding=cfg.file_io)
```

---

## 2. 字符乱码诊断流程（审查时遇到乱码类 Bug 必走）

### 2.1 五步诊断法

```
Step 1: 现象定位
  - UI 显示问号 → 是字符 0x3f 还是字体缺失？
  - 用浏览器 DevTools Network 查看响应 body 真实字符

Step 2: 字节层诊断（绕过 stdout）
  - 用 conn.text_factory = bytes 读取原始字节
  - 打印 codepoints（[hex(b) for b in row[0]]）
  - 确认存储的就是 0x3f（非显示编码问题）

Step 3: 编码链路逐层排查
  - 存储层：PRAGMA encoding（SQLite 默认 UTF-8）
  - ORM 层：SQLAlchemy connect_args charset
  - API 层：json.dumps ensure_ascii 参数
  - HTTP 层：Content-Type charset
  - 客户端层：终端 / 浏览器默认编码

Step 4: 写入源追溯
  - 审计日志：source / ip / user-agent / 时间戳
  - 时间间隔 < 1 秒的批量写入 → 怀疑脚本调用
  - source=web + 无浏览器 UA → 脚本模拟前端调用

Step 5: 根因定位
  - 外部脚本默认编码与 API 期望不一致
  - PowerShell 默认 cp936 / cmd 默认 gbk / requests 默认 UTF-8
```

### 2.2 审查 checklist

| 类别 | 检查项 |
|---|---|
| 文件 I/O | 所有 open / read_text / write_text 显式 encoding？ |
| 数据库 | SQLite 不显式 PRAGMA encoding？MySQL/PG 带 charset？ |
| HTTP 响应 | Content-Type 带 charset？自定义 Response 显式 media_type？ |
| 输入校验 | 写入文本字段前校验非 ASCII 字符不为 `?`？ |
| 审计日志 | 记录 source / UA / IP / 毫秒级时间戳？ |
| 调试脚本 | `_debug_*.py` 已删除？未提交到 git？ |
| 配置管理 | 编码参数走 YAML 配置？未硬编码？ |
| 测试覆盖 | 有编码回归测试？外部脚本调用测试？ |

---

## 3. 复盘反模式（从对话中提炼）

### 3.1 反模式 5：依赖系统默认编码

**复盘案例**：FAQ 数据库存储 ASCII 0x3f 字符

**反模式代码**：
```python
# ❌ 依赖系统默认编码
content = open("data/faq.json").read()  # Windows 上可能 cp936
Path("data/log.txt").write_text(log_content)  # 同上
```

**正确模式**：
```python
# ✅ 显式 UTF-8
content = Path("data/faq.json").read_text(encoding="utf-8")
Path("data/log.txt").write_text(log_content, encoding="utf-8")
```

**预防机制**：审查时 grep `open(` 和 `read_text(` / `write_text(`，检查是否带 `encoding=` 参数。

### 3.2 反模式 6：用 print 诊断字符乱码

**复盘案例**：首次调试 FAQ 乱码时，`print(repr(value))` 仍输出 `'???????'`

**反模式代码**：
```python
# ❌ print 会被 stdout 编码再次编码
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
print(repr(value))  # 仍是 '???????'，因为存储的就是 0x3f
```

**正确模式**：
```python
# ✅ 用 bytes 模式读取，绕过 stdout 编码
import sqlite3
conn = sqlite3.connect("data/xianyu.db")
conn.text_factory = bytes
rows = conn.execute("SELECT question FROM chatbot_faqs").fetchall()
for r in rows:
    print([hex(b) for b in r[0]])  # 看到真实字节 [0x3f, 0x3f, ...]
```

**预防机制**：诊断字符乱码类问题时，必查"是否被 stdout 编码干扰"，用字节级工具验证。

### 3.3 反模式 7：外部脚本调用 API 不显式编码

**复盘案例**：PowerShell 默认 cp936 编码 HTTP body，中文被替换为 `?`

**反模式代码**：
```powershell
# ❌ PowerShell 默认 cp936 编码 body
$body = @{ question = "如何退款" } | ConvertTo-Json
Invoke-RestMethod -Uri "..." -Method Post -Body $body
```

**正确模式**：
```powershell
# ✅ 显式 UTF-8 编码 body
$body = @{ question = "如何退款" } | ConvertTo-Json
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
Invoke-RestMethod -Uri "..." -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes
```

**预防机制**：项目提供标准化外部脚本模板（`scripts/templates/call_api.{ps1,py}`），禁止业务方自行编写调用代码。

### 3.4 反模式 8：临时调试脚本留在仓库

**复盘案例**：FAQ 乱码诊断中产生 `_debug_faq.py` / `_debug_audit.py` 等临时脚本

**反模式代码**：
```bash
# ❌ 临时脚本留在仓库
git add _debug_faq.py
git commit -m "debug"
```

**正确模式**：
```bash
# ✅ 用完即删
del _debug_faq.py _debug_faq_out.txt
# 或加入 .gitignore
echo "_debug_*.py" >> .gitignore
echo "_debug_*.txt" >> .gitignore
```

**预防机制**：`.gitignore` 必须包含 `_debug_*` 模式；审查时如发现 `_debug_*.py` 文件，要求删除。

---

## 4. 测试用例

### 4.1 编码回归测试

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

    conn.text_factory = bytes
    row = conn.execute("SELECT content FROM t").fetchone()
    assert b"?" not in row[0], "存储内容包含 0x3f，编码已损坏"
    assert row[0].decode("utf-8") == "如何退款"

def test_http_api_preserves_chinese(test_client):
    """HTTP API 写入的中文字符必须正确存储。"""
    payload = {"question": "如何退款", "answer": "请联系客服"}
    resp = test_client.post("/api/xxx", json=payload)
    assert resp.status_code == 200

    conn = sqlite3.connect("data/xianyu.db")
    conn.text_factory = bytes
    row = conn.execute("SELECT question FROM xxx ORDER BY id DESC LIMIT 1").fetchone()
    assert b"?" not in row[0], "API 写入的中文字符被替换为 0x3f"
```

### 4.2 配置加载测试

```python
def test_encoding_config_loaded():
    """EncodingConfig 必须从 YAML 加载。"""
    from xianyu_hunter.infra.yaml_config import get_config
    cfg = get_config().encoding
    assert cfg.file_io == "utf-8"
    assert cfg.database == "utf-8"
    assert cfg.http_response == "utf-8"
```

---

## 5. 常用检查脚本

```bash
# grep 检查 open() 是否带 encoding 参数
rg "open\([^)]*\)" src/xianyu_hunter/ | rg -v "encoding="

# grep 检查 read_text / write_text 是否带 encoding 参数
rg "\.(read_text|write_text)\([^)]*\)" src/xianyu_hunter/ | rg -v "encoding="

# grep 检查硬编码编码字符串
rg "\"utf-8\"|'utf-8'" src/xianyu_hunter/

# 检查 _debug_*.py 是否提交
git ls-files | rg "_debug_"

# 检查 .gitignore 包含 _debug_ 模式
rg "_debug_\*" .gitignore
```

---

## 6. 参考

- [PEP 393 - Flexible String Representation](https://peps.python.org/pep-0393/)
- [SQLite Text Encoding](https://www.sqlite.org/pragma.html#pragma_encoding)
- [FastAPI Response](https://fastapi.tiangolo.com/advanced/custom-response/)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/encoding-and-io.md)
- [项目编码规范](../../xianyu-hunter-dev/references/coding-standards.md)
- [后端安全审查](security.md)
- [YAML 配置审查](yaml-and-config.md)

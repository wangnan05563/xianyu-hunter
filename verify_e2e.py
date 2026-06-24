"""P1 字段补齐端到端验证脚本（需闲鱼登录态）

使用方法：
1. 启动后端：python -m xianyu_hunter web --with-scheduler
2. 前端登录闲鱼账号（导入 cookie）
3. 运行本脚本：python verify_e2e.py

成功标志：region/want_cnt/view_cnt 至少 1 个字段从空值变为有值
"""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# 加载 .env 中的 WEB_TOKEN
env_path = Path(__file__).parent / '.env'
WEB_TOKEN = ''
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        if line.startswith('WEB_TOKEN='):
            WEB_TOKEN = line.split('=', 1)[1].strip()
            break

if not WEB_TOKEN:
    print('未找到 WEB_TOKEN，请检查 .env 文件')
    sys.exit(1)

import httpx

BASE = 'http://127.0.0.1:8000'

# 从 items 表自动选最近的一条存在但缺字段的记录
db = sqlite3.connect('data/xianyu.db')
db.row_factory = sqlite3.Row
cur = db.cursor()
row = cur.execute(
    "SELECT id FROM items "
    "WHERE want_cnt = 0 OR want_cnt IS NULL "
    "OR view_cnt = 0 OR view_cnt IS NULL "
    "OR region = '' OR region IS NULL "
    "ORDER BY first_seen DESC LIMIT 1"
).fetchone()
db.close()

if not row:
    print('items 表中没有需要补齐的记录')
    sys.exit(0)

ITEM_ID = row['id']
print('=' * 60)
print(f'P1 端到端验证 - item_id={ITEM_ID}')
print('=' * 60)

# 调用前
db = sqlite3.connect('data/xianyu.db')
db.row_factory = sqlite3.Row
cur = db.cursor()
before = cur.execute(
    'SELECT id, title, region, want_cnt, view_cnt, thumb_url '
    'FROM items WHERE id = ?', (ITEM_ID,)
).fetchone()

print('\n=== 1. 调用前 items 表数据 ===')
if before:
    for k in before.keys():
        print(f'  {k:15s} = {before[k]!r}')

# 调用
print('\n=== 2. 调用 POST /api/evaluations/{item_id}/collect-official ===')
start = time.time()
try:
    resp = httpx.post(
        f'{BASE}/api/evaluations/{ITEM_ID}/collect-official',
        headers={'Authorization': f'Bearer {WEB_TOKEN}'},
        timeout=120.0,
    )
    elapsed = time.time() - start
    print(f'  HTTP 状态: {resp.status_code}  耗时: {elapsed:.1f}s')
    try:
        body = resp.json()
        if isinstance(body, dict):
            for k in ['item_id', 'data_source', 'score', 'risk_level', 'error', 'detail']:
                if k in body:
                    v = str(body[k])
                    print(f'  {k:15s} = {v[:200]!r}')
            if 'item' in body and isinstance(body['item'], dict):
                print('  item 字段:')
                for k in ['title', 'region', 'want_cnt', 'view_cnt', 'thumb_url', 'publish_time']:
                    if k in body['item']:
                        print(f'    {k:15s} = {body["item"][k]!r}')
    except Exception:
        print(f'  响应(非JSON): {resp.text[:500]}')
except httpx.HTTPError as e:
    print(f'  HTTP 异常: {e}')

# 调用后
print('\n=== 3. 调用后 items 表数据 ===')
after = cur.execute(
    'SELECT id, title, region, want_cnt, view_cnt, thumb_url '
    'FROM items WHERE id = ?', (ITEM_ID,)
).fetchone()
if after:
    for k in after.keys():
        print(f'  {k:15s} = {after[k]!r}')

# 字段对比
print('\n=== 4. P1 关键字段对比 ===')
fields = ['region', 'want_cnt', 'view_cnt', 'thumb_url']
improved = 0
for f in fields:
    b = before[f] if before else None
    a = after[f] if after else None
    # 判定有改善：None/空字符串/0 -> 有值
    def _is_empty(v):
        if v is None:
            return True
        if isinstance(v, str) and v == '':
            return True
        if isinstance(v, (int, float)) and v == 0:
            return True
        return False
    b_empty = _is_empty(b)
    a_empty = _is_empty(a)
    if b_empty and not a_empty:
        status = '✅ 新增'
        improved += 1
    elif a != b:
        status = '🔄 更新'
        improved += 1
    else:
        status = '⚠️ 无变化'
    print(f'  {f:15s}: {b!r:30s} -> {a!r:30s}  {status}')

db.close()
print('\n' + '=' * 60)
print(f'改善字段数: {improved}/4')
print('=' * 60)

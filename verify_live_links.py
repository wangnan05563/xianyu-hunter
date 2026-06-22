"""验证 live_links 接口的动态显示方案

调用 live_links 接口，检查：
1. 返回的 field_map 是否正确
2. display 字段是否经过 normalize_display_fields 校正
3. seller_nick/region/publish_time/seller_credit 是否存在错位
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"
TASK_ID = "ta6169110"  # Switch OLED
# 从 .env 读取 token（认证中间件支持 Authorization: Bearer <token>）
WEB_TOKEN = "PgEECYNIneqtk7fb-dyYvA4nzj3YTcjqPOVjZqAJATQ"


def call_api(url: str, timeout: int = 60, retries: int = 3) -> dict:
    """调用 API 并返回 JSON 响应

    503 错误时自动重试（浏览器锁被占用时后端返回 503）
    """
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            # 添加 Bearer Token 认证头
            req.add_header("Authorization", f"Bearer {WEB_TOKEN}")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 503 and attempt < retries - 1:
                print(f"  503 浏览器锁被占用，等待 10 秒后重试 (attempt {attempt + 1}/{retries})...")
                time.sleep(10)
                continue
            print(f"HTTP Error {e.code}: {body[:500]}")
            return {}
        except Exception as e:
            print(f"请求失败: {e}")
            return {}
    return {}


def main() -> int:
    # 1. 获取任务列表
    tasks = call_api(f"{BASE_URL}/api/tasks?limit=10")
    if not tasks:
        print("无法获取任务列表，请检查后端服务是否启动")
        return 1
    print(f"任务列表: {len(tasks.get('items', []))} 个任务")
    for t in tasks.get("items", []):
        print(f"  - {t['id']}: {t.get('name', '')} ({t.get('keyword', '')})")

    # 2. 调用 live_links 接口
    print(f"\n调用 live_links 接口 (task={TASK_ID})...")
    result = call_api(f"{BASE_URL}/api/tasks/{TASK_ID}/links/live", timeout=60)
    if not result:
        print("live_links 接口调用失败")
        return 1

    # 3. 检查返回结果
    print(f"\n=== 返回结果 ===")
    print(f"ok: {result.get('ok')}")
    print(f"keyword: {result.get('keyword')}")
    print(f"session_expired: {result.get('session_expired')}")
    counts = result.get("counts", {})
    print(f"counts: item={counts.get('item', 0)}, seller={counts.get('seller', 0)}, total={counts.get('total', 0)}")

    # 4. 检查 field_map
    field_map = result.get("field_map", {})
    print(f"\n=== field_map (字段元数据) ===")
    if field_map:
        for field, meta in field_map.items():
            print(f"  {field}: label={meta.get('label')}, type={meta.get('type')}, width={meta.get('width')}")
    else:
        print("  (空)")

    # 5. 检查 display 字段
    items = result.get("items", [])
    print(f"\n=== 商品列表 (前 3 条) ===")
    for i, item in enumerate(items[:3]):
        display = item.get("display", {})
        print(f"\n商品 {i + 1}: {display.get('title', '?')[:50]}")
        print(f"  seller_nick:   {display.get('seller_nick', '')!r}")
        print(f"  region:        {display.get('region', '')!r}")
        print(f"  publish_time:  {display.get('publish_time', '')!r}")
        print(f"  seller_credit: {display.get('seller_credit', '')!r}")
        print(f"  price:         {display.get('price', '')!r}")
        print(f"  is_sold:       {display.get('is_sold', '')!r}")

        # 检查字段错位
        nick = display.get("seller_nick", "")
        region = display.get("region", "")
        if nick and ("发布" in nick or "前" in nick or "信用" in nick or "¥" in nick):
            print(f"  ⚠️  警告: seller_nick 疑似错位: {nick!r}")
        if region and ("***" in region or "*" in region):
            print(f"  ⚠️  警告: region 疑似是昵称: {region!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

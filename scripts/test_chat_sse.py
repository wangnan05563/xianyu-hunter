"""测试 Chat API SSE 流式响应

用 httpx 流式模式接收 SSE 事件，验证 RAG 检索 + LLM 回答全链路。
"""
from __future__ import annotations

import json
import sys

import httpx

# 从项目 settings 读取认证 token（与 tests/test_api_anticrawl.py 实践一致），
# 避免硬编码真实凭证到脚本（.env 已被 .gitignore 排除）
from xianyu_hunter.config import get_settings

TOKEN = get_settings().web_token
URL = "http://127.0.0.1:8001/api/chatbot/chat"
MESSAGE = sys.argv[1] if len(sys.argv) > 1 else "闲鱼猎人怎么创建任务？"


def main() -> int:
    headers = {
        "Cookie": f"xh_token={TOKEN}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body = {"session_id": None, "message": MESSAGE}

    print(f"[REQ] POST {URL}")
    print(f"[REQ] message: {MESSAGE}")
    print("-" * 60)

    event_count = 0
    full_answer: list[str] = []

    try:
        with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=2.0)) as client:
            with client.stream("POST", URL, headers=headers, json=body) as resp:
                print(f"[HTTP] status={resp.status_code}")
                print("-" * 60)
                if resp.status_code != 200:
                    print(f"[ERR] 非 200 响应: {resp.text}")
                    return 1

                current_event: str | None = None
                for line in resp.iter_lines():
                    if not line:
                        current_event = None
                        continue
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            print(f"[{current_event or 'data'}] raw: {data_str[:200]}")
                            continue

                        event_count += 1
                        etype = current_event or "data"

                        if etype == "token":
                            # orchestrator TOKEN 事件字段是 content（非 delta）
                            token = data.get("content", "") or data.get("delta", "")
                            full_answer.append(token)
                            print(token, end="", flush=True)
                        elif etype == "sources":
                            sources = data.get("sources", [])
                            print(f"\n[SOURCES] 命中 {len(sources)} 条引用:")
                            for s in sources:
                                print(
                                    f"  [{s.get('index')}] {s.get('file')} > "
                                    f"{s.get('section')} (sim={s.get('similarity')})"
                                )
                        elif etype == "done":
                            # orchestrator DONE 事件字段：content/degraded/metadata
                            print(f"\n\n[DONE] degraded={data.get('degraded')}")
                            print(f"[DONE] content_len={len(data.get('content', '') or '')}")
                            meta = data.get("metadata") or {}
                            print(f"[DONE] metadata_keys={list(meta.keys())}")
                        elif etype == "error":
                            print(f"\n[ERROR] code={data.get('code')} msg={data.get('message')}")
                            return 2
                        elif etype == "escalate":
                            print(f"\n[ESCALATE] reason={data.get('reason')}")
                            print(f"[ESCALATE] contact={data.get('contact')}")
                            return 2
                        else:
                            print(f"\n[{etype}] {json.dumps(data, ensure_ascii=False)[:300]}")

    except httpx.ConnectError as e:
        print(f"[FATAL] 连接失败: {e}")
        return 3
    except httpx.ReadTimeout:
        print("\n[TIMEOUT] 读取超时")
        return 4

    print("\n" + "=" * 60)
    print(f"[SUMMARY] 共收到 {event_count} 个 SSE 事件")
    answer = "".join(full_answer)
    print(f"[SUMMARY] 回答总长: {len(answer)} 字符")
    if answer:
        print(f"[SUMMARY] 回答预览: {answer[:200]}{'...' if len(answer) > 200 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

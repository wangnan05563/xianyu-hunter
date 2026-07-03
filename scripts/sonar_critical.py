"""Query SonarQube for BLOCKER and CRITICAL issues."""
import json
import urllib.request

token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
headers = {"Authorization": f"Bearer {token}"}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main() -> None:
    # BLOCKER 问题
    print("=== BLOCKER Issues ===")
    p = 1
    while True:
        url = (
            f"http://localhost:9000/api/issues/search"
            f"?componentKeys=xianyu_hunter&ps=500&p={p}"
            f"&issueStatuses=OPEN,CONFIRMED"
            f"&severities=BLOCKER"
        )
        data = fetch(url)
        for i in data["issues"]:
            comp = i.get("component", "").replace("xianyu_hunter:", "")
            print(f"  L{i.get('line', '?'):>5}  {i.get('rule', '')}")
            print(f"        {comp}")
            print(f"        {i.get('message', '')[:200]}")
            print()
        if len(data["issues"]) < 500:
            break
        p += 1


if __name__ == "__main__":
    main()

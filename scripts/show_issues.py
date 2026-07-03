"""Show all current issues of a specific file from SonarQube."""
import json
import sys
import urllib.request

token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
headers = {"Authorization": f"Bearer {token}"}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main(keyword: str) -> None:
    # Search current issues containing keyword in component
    all_issues = []
    p = 1
    while True:
        url = (
            f"http://localhost:9000/api/issues/search"
            f"?componentKeys=xianyu_hunter&ps=500&p={p}"
            f"&issueStatuses=OPEN,CONFIRMED"
        )
        data = fetch(url)
        all_issues.extend(data["issues"])
        if len(all_issues) >= data["paging"]["total"]:
            break
        p += 1

    matched = [
        i for i in all_issues
        if keyword.lower() in i.get("component", "").lower()
    ]
    matched.sort(key=lambda x: (x.get("rule", ""), x.get("line", 0)))
    print(f"Found {len(matched)} issues for '{keyword}':\n")
    cur_rule = None
    for i in matched:
        rule = i.get("rule", "")
        if rule != cur_rule:
            print(f"\n--- {rule} ---")
            cur_rule = rule
        line = i.get("line", "?")
        msg = i.get("message", "")[:160]
        clean = i.get("component", "").replace("xianyu_hunter:", "")
        print(f"  L{line:>5}  {clean}")
        print(f"        {msg}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Chatbot")

"""Query SonarQube API for current issue status summary."""
import json
import urllib.request

token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
headers = {"Authorization": f"Bearer {token}"}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main() -> None:
    base = "http://localhost:9000/api/issues/search"
    url = (
        f"{base}?componentKeys=xianyu_hunter"
        "&ps=1&issueStatuses=OPEN,CONFIRMED"
        "&facets=severities,types,rules,files"
    )
    data = fetch(url)
    total = data["paging"]["total"]
    print(f"Total OPEN+CONFIRMED: {total}")

    facets = {f["property"]: f["values"] for f in data.get("facets", [])}

    print("\n=== By Severity ===")
    for v in facets.get("severities", []):
        print(f"  {v['val']:<10}: {v['count']}")

    print("\n=== By Type ===")
    for v in facets.get("types", []):
        print(f"  {v['val']:<15}: {v['count']}")

    print("\n=== Top 25 Rules ===")
    rules = sorted(facets.get("rules", []), key=lambda x: x["count"], reverse=True)[:25]
    for v in rules:
        print(f"  {v['val']:<25}: {v['count']}")

    print("\n=== Top 15 Files ===")
    files = sorted(facets.get("files", []), key=lambda x: x["count"], reverse=True)[:15]
    for v in files:
        print(f"  {v['count']:>4}  {v['val']}")


if __name__ == "__main__":
    main()

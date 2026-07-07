"""按规则列出 SonarQube OPEN 问题，输出到 stdout。"""
import json
import sys
from collections import defaultdict

with open('sonar_open_issues.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

by_rule = defaultdict(list)
for filepath, issues in data.items():
    for i in issues:
        by_rule[i['rule']].append((filepath, i['line'], i['message']))

target_rule = sys.argv[1] if len(sys.argv) > 1 else None
if target_rule:
    for filepath, line, msg in by_rule.get(target_rule, []):
        print(f"{filepath}:{line} - {msg}")
else:
    for rule, items in sorted(by_rule.items(), key=lambda x: -len(x[1])):
        print(f"\n=== {rule} ({len(items)}) ===")
        for filepath, line, msg in items:
            print(f"  {filepath}:{line} - {msg}")

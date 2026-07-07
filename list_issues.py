"""按规则列出 SonarQube OPEN 问题。"""
import json
import sys

with open('sonar_open_issues.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

rule = sys.argv[1] if len(sys.argv) > 1 else 'python:S1481'
for filepath, issues in data.items():
    for i in issues:
        if i['rule'] == rule:
            print(f"{filepath}:{i['line']} - {i['message']}")

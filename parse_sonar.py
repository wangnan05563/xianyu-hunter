"""临时脚本：解析 SonarQube MCP 返回的 JSON 文件并统计 OPEN 问题。"""
import json
import sys
from collections import Counter


def parse(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    prefix = 'The MCP server responded with: '
    idx = raw.find(prefix)
    if idx >= 0:
        raw = raw[idx + len(prefix):]
    raw = raw.strip()
    data = json.loads(raw)
    if isinstance(data, list) and data and isinstance(data[0], dict) and 'text' in data[0]:
        inner = json.loads(data[0]['text'])
    else:
        inner = data
    issues = inner.get('issues', [])
    print(f'Total issues returned: {len(issues)}')
    paging = inner.get('paging')
    print(f'Paging: {paging}')
    print()
    print('=== By status ===')
    for s, c in Counter(i['status'] for i in issues).most_common():
        print(f'{c} {s}')
    open_issues = [i for i in issues if i['status'] == 'OPEN']
    print(f'\nOPEN count: {len(open_issues)}')
    if not open_issues:
        return
    print('\n=== OPEN issues by rule ===')
    for r, c in Counter(i['rule'] for i in open_issues).most_common():
        print(f'{c} {r}')
    print('\n=== OPEN issues by severity ===')
    for s, c in Counter(i['severity'] for i in open_issues).most_common():
        print(f'{c} {s}')
    print('\n=== OPEN issues by file ===')
    for f, c in Counter(i['component'].replace('xianyu_hunter:', '') for i in open_issues).most_common():
        print(f'{c} {f}')
    print('\n=== OPEN issues detail ===')
    for i in open_issues:
        comp = i['component'].replace('xianyu_hunter:', '')
        tr = i.get('textRange', {})
        print(f"[{i['severity']}] {i['rule']} {comp}:{tr.get('startLine', '?')} - {i['message']}")


if __name__ == '__main__':
    parse(sys.argv[1])

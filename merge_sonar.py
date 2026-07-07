"""合并 SonarQube 两页问题数据并按文件分组输出。"""
import json
import sys
from collections import defaultdict


def load_issues(path: str):
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
    return inner.get('issues', [])


def main():
    all_issues = []
    for p in sys.argv[1:]:
        all_issues.extend(load_issues(p))
    open_issues = [i for i in all_issues if i['status'] == 'OPEN']
    print(f'Total OPEN issues: {len(open_issues)}')
    # 按文件分组
    by_file = defaultdict(list)
    for i in open_issues:
        comp = i['component'].replace('xianyu_hunter:', '')
        by_file[comp].append({
            'rule': i['rule'],
            'line': i.get('textRange', {}).get('startLine'),
            'message': i['message'],
            'severity': i['severity'],
        })
    # 输出文件分组
    print(f'\n=== Files with issues ({len(by_file)} files) ===')
    for f in sorted(by_file.keys(), key=lambda x: -len(by_file[x])):
        print(f'{len(by_file[f])} {f}')
    # 保存为 JSON
    out = {f: issues for f, issues in by_file.items()}
    with open('sonar_open_issues.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nSaved to sonar_open_issues.json')


if __name__ == '__main__':
    main()

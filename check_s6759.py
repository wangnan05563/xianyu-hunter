"""检查 S6759 问题位置是否已包含 readonly 标记。"""
import json
import os

with open('sonar_open_issues.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

items = []
for filepath, issues in data.items():
    for i in issues:
        if i['rule'] == 'typescript:S6759':
            items.append((filepath, i['line']))

fixed = 0
not_fixed = []
for filepath, line in items:
    full_path = os.path.join('d:\\code\\otherProjects\\17_xianyu', filepath.replace('/', os.sep))
    if not os.path.exists(full_path):
        not_fixed.append((filepath, line, 'file not found'))
        continue
    with open(full_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # 检查 line-1 到 line+10 行内是否有 readonly
    start = max(0, line - 1)
    end = min(len(lines), line + 15)
    snippet = ''.join(lines[start:end])
    if 'readonly' in snippet:
        fixed += 1
    else:
        not_fixed.append((filepath, line, snippet[:200].replace('\n', ' | ')))

print(f'Fixed (已含 readonly): {fixed}/{len(items)}')
print(f'Not fixed: {len(not_fixed)}')
for filepath, line, snippet in not_fixed[:30]:
    print(f'\n{filepath}:{line}')
    print(f'  {snippet}')

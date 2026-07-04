import json
import sys
import os
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

fp = r'C:\Users\HSPCAD~1\AppData\Local\Temp\trae\toolcall-output\64b1b082-91c4-4079-afc9-2432a456c44a.txt'
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)
payload = json.loads(data[0]['text'])
issues = payload['issues']

out_lines = []
out_lines.append(f'RELIABILITY issues: {len(issues)}')
out_lines.append('')

sev = Counter(i['severity'] for i in issues)
out_lines.append('Severity:')
for k, v in sorted(sev.items()):
    out_lines.append(f'  {k}: {v}')

out_lines.append('')
out_lines.append('Rules:')
rules = Counter(i['rule'] for i in issues)
for k, v in rules.most_common():
    out_lines.append(f'  {v:3d}  {k}')

out_lines.append('')
out_lines.append('Files:')
files = Counter(i['component'].replace('xianyu_hunter:', '') for i in issues)
for k, v in files.most_common():
    out_lines.append(f'  {v:3d}  {k}')

out_lines.append('')
out_lines.append('Detailed:')
for idx, i in enumerate(issues, 1):
    comp = i['component'].replace('xianyu_hunter:', '')
    tr = i.get('textRange', {})
    sl = tr.get('startLine', '?')
    el = tr.get('endLine', '?')
    out_lines.append(f"{idx:3d}. [{i['severity']}] {i['rule']}  {comp}:{sl}-{el}")
    out_lines.append(f"     {i['message']}")

out_path = r'd:\code\otherProjects\17_xianyu\.tmp_rel_issues.txt'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))

print(f'Written to {out_path}, exists={os.path.exists(out_path)}, size={os.path.getsize(out_path) if os.path.exists(out_path) else 0}')
sys.stdout.flush()

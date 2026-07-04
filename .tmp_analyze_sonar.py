import json
from collections import Counter

with open(r'C:\Users\HSPCAD~1\AppData\Local\Temp\trae\toolcall-output\c87fff4e-2632-4aa7-a0d2-5980d444f130.txt', 'r', encoding='utf-8') as f:
    data = json.load(f)

payload = json.loads(data[0]['text'])
issues = payload['issues']

lines = []
lines.append(f'Total issues in page: {len(issues)}')
lines.append(f'Paging total: {payload["paging"]["total"]}')
lines.append('')

sev = Counter(i['severity'] for i in issues)
lines.append('=== Severity ===')
for k, v in sorted(sev.items()):
    lines.append(f'  {k}: {v}')

stat = Counter(i['status'] for i in issues)
lines.append('=== Status ===')
for k, v in sorted(stat.items()):
    lines.append(f'  {k}: {v}')

lines.append('=== Top 30 Rules ===')
rules = Counter(i['rule'] for i in issues)
for k, v in rules.most_common(30):
    lines.append(f'  {v:3d}  {k}')

lines.append('=== Top 30 Files ===')
files = Counter(i['component'].replace('xianyu_hunter:', '') for i in issues)
for k, v in files.most_common(30):
    lines.append(f'  {v:3d}  {k}')

out = '\n'.join(lines)
with open(r'd:\code\otherProjects\17_xianyu\.tmp_sonar_summary.txt', 'w', encoding='utf-8') as f:
    f.write(out)
print(out)

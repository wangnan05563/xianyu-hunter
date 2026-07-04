import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

fp = r'C:\Users\HSPCAD~1\AppData\Local\Temp\trae\toolcall-output\a58159fb-df45-4700-99c5-ebe21891d107.txt'
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)
payload = json.loads(data[0]['text'])
issues = payload['issues']

print(f'=== HIGH-IMPACT ISSUES: {len(issues)} ===')
print()

sev = Counter(i['severity'] for i in issues)
print('--- Severity ---')
for k, v in sorted(sev.items()):
    print(f'  {k}: {v}')

print()
print('--- Rules ---')
rules = Counter(i['rule'] for i in issues)
for k, v in rules.most_common():
    print(f'  {v:3d}  {k}')

print()
print('--- Files ---')
files = Counter(i['component'].replace('xianyu_hunter:', '') for i in issues)
for k, v in files.most_common():
    print(f'  {v:3d}  {k}')

print()
print('--- Detailed ---')
for idx, i in enumerate(issues, 1):
    comp = i['component'].replace('xianyu_hunter:', '')
    tr = i.get('textRange', {})
    sl = tr.get('startLine', '?')
    el = tr.get('endLine', '?')
    print(f"{idx:3d}. [{i['severity']}] {i['rule']}  {comp}:{sl}-{el}")
    print(f"     {i['message']}")

print()
print('=== END ===')
sys.stdout.flush()

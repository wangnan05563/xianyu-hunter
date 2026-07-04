import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

fp = r'C:\Users\HSPCAD~1\AppData\Local\Temp\trae\toolcall-output\c87fff4e-2632-4aa7-a0d2-5980d444f130.txt'
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)
payload = json.loads(data[0]['text'])
issues = payload['issues']

# Write all issues to a CSV-like format
out_path = r'd:\code\otherProjects\17_xianyu\.tmp_all_issues.tsv'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('idx\tseverity\trule\tfile\tstartLine\tendLine\tmessage\n')
    for idx, i in enumerate(issues, 1):
        comp = i['component'].replace('xianyu_hunter:', '')
        tr = i.get('textRange', {}) or {}
        sl = tr.get('startLine', '')
        el = tr.get('endLine', '')
        msg = i['message'].replace('\t', ' ').replace('\n', ' ')
        f.write(f"{idx}\t{i['severity']}\t{i['rule']}\t{comp}\t{sl}\t{el}\t{msg}\n")

print(f'Wrote {len(issues)} issues to {out_path}')
print(f'File exists: {os.path.exists(out_path)}')
print(f'File size: {os.path.getsize(out_path)}')
sys.stdout.flush()

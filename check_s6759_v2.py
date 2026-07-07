"""更准确地检查 S6759：扫描文件中所有 interface 块，检查字段是否全为 readonly。"""
import json
import os
import re


def check_file_interface_readonly(filepath: str) -> tuple[bool, list]:
    """返回 (all_readonly, missing_fields)"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    # 匹配 interface XxxProps { ... } 块（含 Props 字样）
    pattern = re.compile(
        r'interface\s+(\w*Props\w*|\w*Props)\s*(?:<[^>]+>)?\s*\{([^{}]*?)\}',
        re.DOTALL
    )
    all_readonly = True
    missing = []
    for m in pattern.finditer(content):
        iface_name = m.group(1)
        body = m.group(2)
        for line in body.split('\n'):
            stripped = line.lstrip()
            if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue
            # 字段：name: type 或 name?: type
            field_match = re.match(r'^(readonly\s+)?(\w+)(\??\s*:[^=].*?)(,?;?\s*)$', stripped)
            if field_match:
                if not field_match.group(1):
                    all_readonly = False
                    missing.append(f'{iface_name}.{field_match.group(2)}')
    return all_readonly, missing


if __name__ == '__main__':
    with open('sonar_open_issues.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    items = []
    for filepath, issues in data.items():
        for i in issues:
            if i['rule'] == 'typescript:S6759':
                items.append(filepath)
    items = list(set(items))
    print(f'S6759 files: {len(items)}')
    fixed = 0
    not_fixed = []
    for filepath in items:
        full = os.path.join(r'd:\code\otherProjects\17_xianyu', filepath.replace('/', os.sep))
        if not os.path.exists(full):
            continue
        ok, missing = check_file_interface_readonly(full)
        if ok:
            fixed += 1
        else:
            not_fixed.append((filepath, missing))
    print(f'All readonly: {fixed}/{len(items)}')
    print(f'Not fixed: {len(not_fixed)}')
    for filepath, missing in not_fixed:
        print(f'\n{filepath}:')
        for m in missing:
            print(f'  - {m}')

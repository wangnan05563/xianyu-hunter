"""批量给前端 Props interface 字段加 readonly（S6759 修复）。

策略：扫描文件中所有 `interface XxxProps { ... }` 或 `interface Xxx { ... }` 块
（仅处理含 Props 字样的或被函数组件直接使用的 interface），
给字段前加 readonly（如果还没有）。
"""
import os
import re
import sys


def add_readonly_to_interface(content: str) -> tuple[str, int]:
    """给所有 interface 块的非 readonly 字段加 readonly 前缀"""
    pattern = re.compile(
        r'(interface\s+\w+\s*(?:<[^>]+>)?\s*\{)([^{}]*?)(\})',
        re.DOTALL
    )
    count = 0

    def replacer(m):
        nonlocal count
        header = m.group(1)
        body = m.group(2)
        footer = m.group(3)
        new_lines = []
        for line in body.split('\n'):
            # 跳过空行和注释行
            stripped = line.lstrip()
            if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
                new_lines.append(line)
                continue
            # 匹配字段：`  name: type` 或 `  name?: type` 或 `  name: type,`
            # 不匹配已 readonly 的字段、方法（带括号）、索引签名（带 [）
            field_match = re.match(r'^(\s*)(readonly\s+)?(\w+)(\??\s*:[^=].*?)(,?;?\s*)$', line)
            if field_match and not field_match.group(2):
                indent = field_match.group(1)
                name = field_match.group(3)
                rest = field_match.group(4)
                end = field_match.group(5)
                # 跳过 constructor、方法（含括号）
                if name == 'constructor' or '(' in rest:
                    new_lines.append(line)
                    continue
                new_line = f'{indent}readonly {name}{rest}{end}'
                new_lines.append(new_line)
                count += 1
            else:
                new_lines.append(line)
        return header + '\n'.join(new_lines) + footer

    new_content = pattern.sub(replacer, content)
    return new_content, count


def add_readonly_to_inline_props(content: str) -> tuple[str, int]:
    """给函数组件 inline props 类型加 readonly：function Foo(props: { name: string }) -> { readonly name: string }

    匹配 `: {` 后到 `}` 的 inline 对象类型（非 interface）。
    """
    # 匹配 `: {\n ... \n}` 形式的 inline 类型注解（解构或普通 props）
    # 这个正则较保守，只匹配函数参数位置的 inline 对象类型
    pattern = re.compile(
        r'(\})\s*:\s*(\{)([^{}]*?)(\})',
        re.DOTALL
    )
    count = 0

    def replacer(m):
        nonlocal count
        pre = m.group(1)
        open_brace = m.group(2)
        body = m.group(3)
        close_brace = m.group(4)
        # 如果 body 已全为 readonly，跳过
        if 'readonly' in body and not re.search(r'^\s*\w+\??\s*:', body, re.MULTILINE):
            return m.group(0)
        new_lines = []
        for line in body.split('\n'):
            stripped = line.lstrip()
            if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
                new_lines.append(line)
                continue
            field_match = re.match(r'^(\s*)(readonly\s+)?(\w+)(\??\s*:[^=].*?)(,?;?\s*)$', line)
            if field_match and not field_match.group(2):
                indent = field_match.group(1)
                name = field_match.group(3)
                rest = field_match.group(4)
                end = field_match.group(5)
                if name == 'constructor' or '(' in rest:
                    new_lines.append(line)
                    continue
                new_line = f'{indent}readonly {name}{rest}{end}'
                new_lines.append(new_line)
                count += 1
            else:
                new_lines.append(line)
        return f'{pre}: {open_brace}' + '\n'.join(new_lines) + f'{close_brace}'

    new_content = pattern.sub(replacer, content)
    return new_content, count


def process_file(filepath: str) -> int:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content, count1 = add_readonly_to_interface(content)
    new_content, count2 = add_readonly_to_inline_props(new_content)
    total = count1 + count2
    if total > 0 and new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
    return total


if __name__ == '__main__':
    base = r'd:\code\otherProjects\17_xianyu'
    files_to_process = [
        # S6759 未修复的文件列表
        r'frontend\src\pages\Config\EvalRules.tsx',
        r'frontend\src\components\layout\AccountSwitcher.tsx',
        r'frontend\src\pages\Evaluations\components\AIEvalModal.tsx',
        r'frontend\src\pages\Evaluations\components\CollectResultModal.tsx',
        r'frontend\src\pages\Evaluations\components\DeepAnalyzeModal.tsx',
        r'frontend\src\pages\PriceDashboard\components\BargainEvalCard.tsx',
        r'frontend\src\pages\PriceDashboard\components\CategoryComparisonChart.tsx',
        r'frontend\src\pages\PriceDashboard\components\CategoryStatsTable.tsx',
        r'frontend\src\pages\PriceDashboard\components\SoldRangeCard.tsx',
        r'frontend\src\mobile\components\PullToRefresh.tsx',
        r'frontend\src\pages\Dashboard\components\PriceHistogramCard.tsx',
        r'frontend\src\pages\Orders\Orders.tsx',
        r'frontend\src\components\SheetWorkspace\SheetPreferences.tsx',
        r'frontend\src\pages\Chatbot\components\ChatbotOnboarding.tsx',
        r'frontend\src\pages\Chatbot\components\QuickReplyChips.tsx',
        r'frontend\src\pages\Config\AIConfig\components\EmbeddingConfigForm.tsx',
        r'frontend\src\pages\About\AboutMenuList.tsx',
        r'frontend\src\pages\About\BrandCard.tsx',
        r'frontend\src\pages\About\OpenSourceLicenses.tsx',
        r'frontend\src\pages\Chatbot\components\KBStatusCard.tsx',
        r'frontend\src\pages\Dashboard\components\KpiSection.tsx',
        r'frontend\src\components\ExportButton.tsx',
        r'frontend\src\pages\Config\NotifierChannels\components\ChannelCard.tsx',
        r'frontend\src\pages\Dashboard\components\EvalFunnelCard.tsx',
        r'frontend\src\pages\Evaluations\components\CollapsibleRail.tsx',
        r'frontend\src\pages\Evaluations\components\ColumnSettingsModal.tsx',
        r'frontend\src\pages\Config\AIConfig\components\BudgetSettings.tsx',
        r'frontend\src\pages\Config\AIConfig\components\UsageStats.tsx',
        r'frontend\src\pages\Config\NotifierChannels\components\QuietHoursTimeline.tsx',
        r'frontend\src\pages\Config\NotifierChannels\components\SortableChannelItem.tsx',
    ]
    total_count = 0
    for rel in files_to_process:
        full = os.path.join(base, rel)
        if not os.path.exists(full):
            print(f'NOT FOUND: {rel}')
            continue
        n = process_file(full)
        if n > 0:
            print(f'  {rel}: +{n} readonly')
            total_count += n
    print(f'\nTotal: {total_count} readonly added')

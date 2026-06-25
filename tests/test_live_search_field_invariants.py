"""字段结构不变量测试：item 行与 seller 行的 display 字段必须对称。

背景：ItemList 表格的列渲染逻辑（标题/价格/卖家/发布时间等）假设每一行
都拥有完整的 display 字段。如果 seller 行缺少部分字段，会出现"卖家"列与
"发布时间"列错位显示同一 seller_credit 的问题。

本测试静态校验 live_search 中两条 seller-row 构造路径的字段集合，
防止以后有人改回不对称的结构。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEARCH_PY = REPO / "src" / "xianyu_hunter" / "modules" / "collector" / "_search.py"


# 字段名清单：item 行和 seller 行都必须具备（值允许为空）
REQUIRED_DISPLAY_FIELDS = {
    "title",
    "brand",
    "price",
    "thumb_url",
    "region",
    "url",
    "is_sold",
    "publish_time",
    "seller_id",
    "seller_nick",
    "seller_credit",
    "want_cnt",
    "view_cnt",
    "link_type",
    "link_key",
}


def _extract_dict_literals(tree: ast.AST) -> list[ast.Dict]:
    """提取模块中所有的 dict 字面量"""
    return [node for node in ast.walk(tree) if isinstance(node, ast.Dict)]


def _dict_keys(node: ast.Dict) -> set[str]:
    """从 AST dict 节点中提取字符串 key"""
    keys: set[str] = set()
    for k in node.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.add(k.value)
    return keys


def _find_seller_dicts(tree: ast.AST) -> list[ast.Dict]:
    """找出包含 'link_type': 'seller' 字面量键对的 dict 节点"""
    out: list[ast.Dict] = []
    for d in _extract_dict_literals(tree):
        keys = _dict_keys(d)
        if "link_type" in keys and "seller_id" in keys and "link_key" in keys:
            out.append(d)
    return out


def test_seller_rows_have_symmetric_fields() -> None:
    """live_search 中所有 seller 行的 dict 必须与 item 行共享关键字段集合"""
    source = SEARCH_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    seller_dicts = _find_seller_dicts(tree)
    # 至少有两个：API 模式 + DOM 回退模式
    assert len(seller_dicts) >= 2, (
        f"未找到 seller 行构造代码（期望至少 2 个），实际 {len(seller_dicts)} 个"
    )
    for idx, d in enumerate(seller_dicts):
        keys = _dict_keys(d)
        missing = REQUIRED_DISPLAY_FIELDS - keys
        assert not missing, (
            f"第 {idx} 个 seller 行缺少字段: {sorted(missing)}\n"
            f"当前字段: {sorted(keys)}\n"
            f"前端表格列需要这些字段用于统一渲染，缺失将导致列错位"
        )


def test_seller_rows_use_seller_nick_for_title() -> None:
    """seller 行的 title 字段值必须使用 seller_nick，禁止误塞商品标题

    通过 AST 静态分析：检查每个 seller dict 中 title 字段对应的值表达式，
    必须包含 seller_nick 或字面量 "卖家 ..." 前缀。
    """
    source = SEARCH_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    seller_dicts = _find_seller_dicts(tree)
    assert seller_dicts, "未找到 seller 行构造代码"

    for idx, d in enumerate(seller_dicts):
        # 遍历 dict 的 (key, value) 节点对
        for k, v in zip(d.keys, d.values):
            if not (isinstance(k, ast.Constant) and k.value == "title"):
                continue
            # value 必须是 Name(seller_nick) / JoinedStr(f"...")/ FormattedValue 等
            # 简单方式：序列化 value 节点并检查关键 token
            snippet = ast.unparse(v)
            assert ("seller_nick" in snippet) or ("卖家" in snippet), (
                f"第 {idx} 个 seller 行 title 字段值来源可疑（{snippet!r}），"
                f"可能误用了商品标题，会导致前端表格列错位"
            )

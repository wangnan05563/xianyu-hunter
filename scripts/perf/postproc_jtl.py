#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 gen_jmx.py 的端点清单(每个接口的预期响应码)重算 JTL 的 success 字段。

背景: JMeter ResponseAssertion 在 test_type=Matches 下对 4xx 响应码的判定存在已知
ORO 正则怪异行为(2xx 通过、4xx 不通过)，导致 success 字段不可靠。但 responseCode
是可靠的，因此这里用「实际响应码 ∈ 预期码集合」重算 success，得到可信的错误率。

用法:
  python postproc_jtl.py <input.jtl> [output.jtl]
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import gen_jmx  # noqa: E402


def build_expect():
    expect = {}
    for ep in gen_jmx.READS + gen_jmx.WRITES:
        label = ep[2]
        codes = ep[4]
        expect[label] = set(c.strip() for c in codes.split("|") if c.strip())
    return expect


def main():
    if len(sys.argv) < 2:
        print("usage: postproc_jtl.py <input.jtl> [output.jtl]")
        return 1
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else (src[:-4] + "_fixed.jtl")
    expect = build_expect()
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    if not rows:
        print("empty JTL:", src)
        return 1
    fixed = 0
    for r in rows:
        exp = expect.get(r["label"], set())
        ok = r["responseCode"] in exp
        r["success"] = "true" if ok else "false"
        if ok:
            fixed += 1
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("postproc %s  rows=%d  success=%d  unexpected=%d  -> %s"
          % (src, len(rows), fixed, len(rows) - fixed, dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())

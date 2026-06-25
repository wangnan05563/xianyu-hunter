"""多场景测试：验证不同评分区间的抢单触发规则

测试修复后的 should_pass / should_auto_buy 逻辑：
- pass_score=60（推送门槛）
- auto_buy_score=75（抢单门槛）

预期行为：
- < 60 分：不推送，不抢单
- 60-74 分：推送通知，但不抢单
- 75+ 分且 LOW 风险：推送通知 + 抢单
- 任何分数但 EXTREME/UNKNOWN 风险：不推送，不抢单
"""
from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel


def make_eval(score: int, risk: RiskLevel) -> EvalResult:
    """构造测试用 EvalResult"""
    return EvalResult(
        score=score,
        risk_level=risk,
        dimension_scores={"professional": 20, "credit": 25, "dispute": 20, "price": 12},
        reject_reasons=[],
        data_quality="full",
    )


# 配置阈值（与 config.yaml 一致）
PASS_SCORE = 60
AUTO_BUY_SCORE = 75

test_cases = [
    # (描述, score, risk, 期望should_pass, 期望should_auto_buy)
    ("77分 LOW风险（用户问题场景）", 77, RiskLevel.LOW, True, True),
    ("75分 LOW风险（刚好达到抢单线）", 75, RiskLevel.LOW, True, True),
    ("74分 MEDIUM风险（低于抢单线）", 74, RiskLevel.MEDIUM, True, False),
    ("70分 MEDIUM风险（中等分数）", 70, RiskLevel.MEDIUM, True, False),
    ("60分 MEDIUM风险（刚好达到推送线）", 60, RiskLevel.MEDIUM, True, False),
    ("59分 HIGH风险（低于推送线）", 59, RiskLevel.HIGH, False, False),
    ("40分 HIGH风险（低分）", 40, RiskLevel.HIGH, False, False),
    ("85分 LOW风险（高分）", 85, RiskLevel.LOW, True, True),
    ("100分 LOW风险（满分）", 100, RiskLevel.LOW, True, True),
    ("77分 EXTREME风险（一票否决）", 77, RiskLevel.EXTREME, False, False),
    ("77分 UNKNOWN风险（数据不足）", 77, RiskLevel.UNKNOWN, False, False),
    ("None分 UNKNOWN风险（无分数）", None, RiskLevel.UNKNOWN, False, False),
]

print(f"配置: pass_score={PASS_SCORE}, auto_buy_score={AUTO_BUY_SCORE}")
print("=" * 90)
print(f"{'描述':<35} {'分数':<6} {'风险':<10} {'推送':<6} {'抢单':<6} {'推送结果':<10} {'抢单结果':<10} {'状态'}")
print("=" * 90)

all_passed = True
for desc, score, risk, exp_pass, exp_buy in test_cases:
    ev = make_eval(score, risk)
    act_pass = ev.should_pass(PASS_SCORE)
    act_buy = ev.should_auto_buy(AUTO_BUY_SCORE)
    status = "✓" if (act_pass == exp_pass and act_buy == exp_buy) else "✗ FAIL"
    if status != "✓":
        all_passed = False
    print(f"{desc:<35} {str(score):<6} {risk.value:<10} {str(exp_pass):<6} {str(exp_buy):<6} {str(act_pass):<10} {str(act_buy):<10} {status}")

print("=" * 90)
if all_passed:
    print("✅ 全部测试通过")
else:
    print("❌ 存在失败用例")

# 额外验证：向后兼容性（is_passed / is_auto_buy property 仍可用）
print("\n--- 向后兼容性验证 ---")
ev = make_eval(77, RiskLevel.LOW)
print(f"77分 LOW: is_passed={ev.is_passed}, is_auto_buy={ev.is_auto_buy} (property, 硬编码>=60/>=80)")
print(f"77分 LOW: should_pass(60)={ev.should_pass(60)}, should_auto_buy(75)={ev.should_auto_buy(75)} (方法, 配置阈值)")

# 验证 RiskLevel 导入（worker.py 修复）
print("\n--- RiskLevel 导入验证（worker.py）---")
try:
    from xianyu_hunter.modules.worker import TaskWorker
    # 确认 worker.py 中 RiskLevel 可访问（修复 NameError）
    import xianyu_hunter.modules.worker as worker_mod
    assert hasattr(worker_mod, 'RiskLevel'), "worker 模块未暴露 RiskLevel"
    print("✓ worker.py RiskLevel 导入正常（NameError 已修复）")
except Exception as e:
    print(f"✗ worker.py RiskLevel 导入失败: {e}")

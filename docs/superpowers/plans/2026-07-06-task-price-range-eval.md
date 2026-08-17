# Task Price Range Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make evaluator price scoring account for task-level min/max price ranges, so items inside ranges such as 600-800 receive differentiated price scores.

**Architecture:** Add a small immutable price range context passed optionally into `Evaluator.evaluate`. Keep existing callers compatible while wiring task-aware paths to pass `PriceConfig` values already produced by `PriceStrategy`.

**Tech Stack:** Python dataclasses, pytest, existing `PriceConfig`/`PriceStrategy`, existing FastAPI route helpers.

---

### Task 1: Price Range Scoring Core

**Files:**
- Modify: `backend/xianyu_hunter/modules/evaluator.py`
- Test: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

Add tests that call `Evaluator.evaluate(item, seller, price_range=PriceRange(min_price=600, max_price=800))` and assert midpoint items score higher than edge items, edge items score higher than out-of-range items, and legacy calls still produce the old price score.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest -q tests/test_evaluator.py::test_task_price_range_scores_center_higher_than_edges tests/test_evaluator.py::test_task_price_range_penalizes_out_of_range_without_hardcoding tests/test_evaluator.py::test_eval_price_without_task_range_keeps_legacy_score`

Expected: FAIL because `PriceRange` and `price_range` are not implemented.

- [ ] **Step 3: Implement minimal core**

Create `PriceRange`, extend `evaluate`, `_evaluate_full`, `_evaluate_partial`, `_evaluate_insufficient`, and `_eval_price` to accept optional range context. Add normalized scoring: center band gets no penalty, near lower/upper edges get small penalties, slight out-of-range gets stronger penalty, obvious out-of-range gets heavy penalty.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest -q tests/test_evaluator.py::test_task_price_range_scores_center_higher_than_edges tests/test_evaluator.py::test_task_price_range_penalizes_out_of_range_without_hardcoding tests/test_evaluator.py::test_eval_price_without_task_range_keeps_legacy_score`

Expected: PASS.

### Task 2: Wire Task Price Context

**Files:**
- Modify: `backend/xianyu_hunter/modules/worker.py`
- Modify: `backend/xianyu_hunter/modules/collection_service.py`
- Modify: `backend/xianyu_hunter/web/routes/api_evaluations.py`
- Modify: `backend/xianyu_hunter/web/routes/api_task_links.py`
- Test: `tests/test_evaluator.py`

- [ ] **Step 1: Add helper and tests**

Add a helper that converts an existing `PriceStrategy` or task raw dict into evaluator price range context. Add tests for conversion from min/max and one-sided ranges.

- [ ] **Step 2: Run helper tests to verify RED**

Run: `pytest -q tests/test_evaluator.py::test_price_range_from_price_config tests/test_evaluator.py::test_price_range_ignores_empty_config`

Expected: FAIL until helper exists.

- [ ] **Step 3: Wire call sites**

Pass `price_range=PriceRange.from_price_config(...)` in worker, collection service, recompute, batch evaluation, and live task links where task-level price strategy is already available.

- [ ] **Step 4: Run focused tests**

Run: `pytest -q tests/test_evaluator.py tests/test_evaluations_price_filter.py tests/test_worker_scheduler.py tests/test_worker_auto_collect.py`

Expected: PASS.

### Task 3: Consistency Cleanup and Verification

**Files:**
- Modify: `backend/xianyu_hunter/modules/evaluator.py`
- Modify: `backend/xianyu_hunter/infra/yaml_config.py`
- Test: `tests/test_evaluator.py`

- [ ] **Step 1: Fix credit threshold fallback**

Align `EvaluationThresholds.credit_score_min` and `EvalThresholds.credit_score_min` default to `60` to match the active YAML and 0-100 credit score comments.

- [ ] **Step 2: Verify full backend focus**

Run: `pytest -q tests/test_evaluator.py tests/test_price_strategy.py tests/test_evaluations_price_filter.py tests/test_worker_scheduler.py tests/test_worker_auto_collect.py`

Expected: PASS.

- [ ] **Step 3: Review diff**

Run: `git diff -- backend/xianyu_hunter/modules/evaluator.py backend/xianyu_hunter/infra/yaml_config.py backend/xianyu_hunter/modules/worker.py backend/xianyu_hunter/modules/collection_service.py backend/xianyu_hunter/web/routes/api_evaluations.py backend/xianyu_hunter/web/routes/api_task_links.py tests/test_evaluator.py`

Expected: Only scoped evaluator, wiring, and tests changes.

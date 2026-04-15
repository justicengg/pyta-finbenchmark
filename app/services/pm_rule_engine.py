"""
Reasoning Error rule engine for primary-market eval cases.

Pure-function rules that detect logical flaws in report_snapshot.
No I/O, ms-level execution.
"""

from __future__ import annotations

SCORE_MAP = {"high": 2, "medium": 1, "low": 0}


def detect_reasoning_errors(report_snapshot: dict) -> list[dict]:
    """Run all rules against a report_snapshot, return detected issues."""
    issues: list[dict] = []
    for rule_fn in ALL_RULES:
        result = rule_fn(report_snapshot)
        if result is not None:
            issues.append(result)
    return issues


# ---------------------------------------------------------------------------
# RE-001: 假设-fork 标记不一致
# ---------------------------------------------------------------------------


def check_re_001(snapshot: dict) -> dict | None:
    items = snapshot.get("key_assumptions", {}).get("items", [])
    mismatched = []
    for item in items:
        level = item.get("level")
        triggers = item.get("triggers_path_fork", False)
        if (level == "hard" and not triggers) or (level == "soft" and triggers):
            mismatched.append(
                {
                    "description": item.get("description", ""),
                    "level": level,
                    "triggers_path_fork": triggers,
                }
            )
    if not mismatched:
        return None
    return {
        "issue_type": "reasoning_error",
        "severity": "medium",
        "stage": "assumption",
        "dimension": None,
        "expected": "hard 假设应设 triggers_path_fork=true，soft 假设应设为 false",
        "actual": f"发现 {len(mismatched)} 个假设的 level 与 triggers_path_fork 标记不一致",
        "evidence": {"rule_id": "RE-001", "mismatched_assumptions": mismatched},
        "root_cause_hint": "LLM 在假设生成时未正确遵循 triggers_path_fork 标注规则",
        "action_suggestion": "在假设生成 prompt 中明确 hard→triggers_path_fork=true 的对应关系",
        "attribution_hint": "prompt",
        "detected_by": "rule_engine",
    }


# ---------------------------------------------------------------------------
# RE-002: 市场有效性-竞争格局矛盾
# ---------------------------------------------------------------------------


def check_re_002(snapshot: dict) -> dict | None:
    assessments = snapshot.get("uncertainty_map", {}).get("assessments", {})
    market = assessments.get("market_validity", {})
    competition = assessments.get("competition", {})

    if market.get("score") != "high" or competition.get("score") != "low":
        return None

    fork_triggers = [f.get("trigger") for f in snapshot.get("path_forks", [])]
    if "macro_timing_mismatch" in fork_triggers:
        return None

    return {
        "issue_type": "reasoning_error",
        "severity": "high",
        "stage": "dimension_analysis",
        "dimension": "market_validity",
        "expected": "市场有效性高不确定 + 竞争低不确定应触发 MACRO_TIMING_MISMATCH 路径分叉",
        "actual": "market_validity=HIGH, competition=LOW 但无对应 path_fork",
        "evidence": {
            "rule_id": "RE-002",
            "market_validity_score": "high",
            "competition_score": "low",
            "path_fork_triggers": fork_triggers,
        },
        "root_cause_hint": "PathForkService 的 _check_macro_timing_mismatch 可能因 founder_analysis 缺失未执行",
        "action_suggestion": "确保 PathForkService 在 market_validity=HIGH 时始终检查 macro_timing_mismatch",
        "attribution_hint": "orchestrator",
        "detected_by": "rule_engine",
    }


# ---------------------------------------------------------------------------
# RE-003: Benchmark lens 与 verdict 不一致
# ---------------------------------------------------------------------------


def check_re_003(snapshot: dict) -> dict | None:
    benchmark = snapshot.get("benchmark_comparison")
    if not benchmark:
        return None

    delta = benchmark.get("confidence_delta")
    if delta is None or delta >= -0.05:
        return None

    decision = snapshot.get("decision", "")
    if decision != "invest":
        return None

    return {
        "issue_type": "reasoning_error",
        "severity": "high",
        "stage": "lens",
        "dimension": None,
        "expected": "当 benchmark 比较拉低置信度 (delta < -0.05) 时，不应直接推荐 invest",
        "actual": f"benchmark confidence_delta={delta}, 但 decision=invest",
        "evidence": {
            "rule_id": "RE-003",
            "benchmark_confidence_delta": delta,
            "decision": decision,
            "benchmark_summary": benchmark,
        },
        "root_cause_hint": "verdict pipeline 可能未充分考虑 benchmark lens 的负面信号",
        "action_suggestion": "在 verdict 合成时，当 benchmark delta 显著为负时自动降级决策",
        "attribution_hint": "orchestrator",
        "detected_by": "rule_engine",
    }


# ---------------------------------------------------------------------------
# RE-004: Monitoring trigger 缺失
# ---------------------------------------------------------------------------


def check_re_004(snapshot: dict) -> dict | None:
    decision = snapshot.get("decision", "")
    if decision not in ("invest", "priority_diligence"):
        return None

    triggers = snapshot.get("monitoring_triggers") or []
    if len(triggers) >= 2:
        return None

    return {
        "issue_type": "reasoning_error",
        "severity": "medium",
        "stage": "monitoring",
        "dimension": None,
        "expected": "积极投资决策应有 ≥2 个后续监测触发条件",
        "actual": f"decision={decision}, 但仅有 {len(triggers)} 个 monitoring_triggers",
        "evidence": {
            "rule_id": "RE-004",
            "decision": decision,
            "trigger_count": len(triggers),
            "monitoring_triggers": triggers,
        },
        "root_cause_hint": "monitoring trigger 生成 prompt 可能未强调最低数量要求",
        "action_suggestion": "在 prompt 中明确要求 invest/priority_diligence 决策必须生成 ≥2 个 trigger",
        "attribution_hint": "prompt",
        "detected_by": "rule_engine",
    }


# ---------------------------------------------------------------------------
# RE-005: 跨轮信号震荡
# ---------------------------------------------------------------------------


def check_re_005(snapshot: dict) -> dict | None:
    trace = snapshot.get("reasoning_trace")
    if not trace:
        return None

    round_traces = trace.get("round_traces", [])
    if len(round_traces) < 2:
        return None

    oscillations = []
    for i in range(len(round_traces) - 1):
        dims_a = round_traces[i].get("dimensions", {})
        dims_b = round_traces[i + 1].get("dimensions", {})
        all_dims = set(dims_a.keys()) & set(dims_b.keys())
        for dim in all_dims:
            score_a = dims_a[dim].get("score", "")
            score_b = dims_b[dim].get("score", "")
            val_a = SCORE_MAP.get(score_a)
            val_b = SCORE_MAP.get(score_b)
            if val_a is not None and val_b is not None and abs(val_a - val_b) >= 2:
                oscillations.append(
                    {
                        "dimension": dim,
                        "round_a": i + 1,
                        "score_a": score_a,
                        "round_b": i + 2,
                        "score_b": score_b,
                    }
                )

    if not oscillations:
        return None

    first = oscillations[0]
    return {
        "issue_type": "reasoning_error",
        "severity": "high",
        "stage": "dimension_analysis",
        "dimension": first["dimension"],
        "expected": "相邻轮次同一维度的不确定性评分不应剧烈震荡",
        "actual": (
            f"维度 {first['dimension']} 在 round {first['round_a']} 为 {first['score_a']}，"
            f"round {first['round_b']} 为 {first['score_b']}"
        ),
        "evidence": {"rule_id": "RE-005", "oscillations": oscillations},
        "root_cause_hint": "维度 agent 在不同轮次对同一信号的解读不一致，可能缺乏跨轮记忆注入",
        "action_suggestion": "在维度 agent 的 prompt 中注入上一轮该维度的评分和论据，确保跨轮一致性",
        "attribution_hint": "orchestrator",
        "detected_by": "rule_engine",
    }


# ---------------------------------------------------------------------------
# RE-006: 置信度与不确定性矛盾
# ---------------------------------------------------------------------------


def check_re_006(snapshot: dict) -> dict | None:
    confidence = snapshot.get("confidence")
    if confidence is None or confidence <= 0.8:
        return None

    assessments = snapshot.get("uncertainty_map", {}).get("assessments", {})
    high_dims = [
        dim for dim, info in assessments.items() if info.get("score") == "high"
    ]

    if len(high_dims) < 2:
        return None

    return {
        "issue_type": "reasoning_error",
        "severity": "critical",
        "stage": "verdict",
        "dimension": None,
        "expected": "当 ≥2 个维度存在高不确定性时，综合置信度不应超过 0.8",
        "actual": f"confidence={confidence}, 但有 {len(high_dims)} 个 HIGH 不确定性维度: {high_dims}",
        "evidence": {
            "rule_id": "RE-006",
            "confidence": confidence,
            "high_dims": high_dims,
            "high_count": len(high_dims),
        },
        "root_cause_hint": "verdict pipeline 的 _resolve_decision 可能未充分惩罚多维度高不确定性",
        "action_suggestion": "在 confidence 计算逻辑中，当 HIGH 维度 ≥2 时自动 cap 到 0.8",
        "attribution_hint": "orchestrator",
        "detected_by": "rule_engine",
    }


# ---------------------------------------------------------------------------
# RE-007: path_forks 数量与 verdict 脱节
# ---------------------------------------------------------------------------


def check_re_007(snapshot: dict) -> dict | None:
    decision = snapshot.get("decision", "")
    confidence = snapshot.get("confidence", 0)

    if decision != "invest" or confidence <= 0.85:
        return None

    forks = snapshot.get("path_forks", [])
    unverified = [f for f in forks if f.get("trigger") == "hard_assumption_unverified"]

    if len(unverified) < 3:
        return None

    return {
        "issue_type": "reasoning_error",
        "severity": "high",
        "stage": "fork",
        "dimension": None,
        "expected": "当 ≥3 个硬假设未验证时，不应同时给出 invest 决策和 >0.85 的高置信度",
        "actual": f"{len(unverified)} 个未验证硬假设 fork, decision={decision}, confidence={confidence}",
        "evidence": {
            "rule_id": "RE-007",
            "unverified_fork_count": len(unverified),
            "decision": decision,
            "confidence": confidence,
            "fork_assumptions": [
                f.get("trigger_assumption", "") for f in unverified[:5]
            ],
        },
        "root_cause_hint": "verdict pipeline 可能未将 unverified hard assumption 数量作为置信度惩罚因子",
        "action_suggestion": "在 verdict 合成时，当 unverified hard forks ≥3 时自动降级到 priority_diligence",
        "attribution_hint": "orchestrator",
        "detected_by": "rule_engine",
    }


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

ALL_RULES = [
    check_re_001,
    check_re_002,
    check_re_003,
    check_re_004,
    check_re_005,
    check_re_006,
    check_re_007,
]

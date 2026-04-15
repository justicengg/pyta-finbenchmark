from app.services.pm_rule_engine import (
    check_re_001,
    check_re_002,
    check_re_003,
    check_re_004,
    check_re_005,
    check_re_006,
    check_re_007,
    detect_reasoning_errors,
)

# ── RE-001: 假设-fork 标记不一致 ──────────────────────────────────────────


def test_re_001_triggers():
    snapshot = {
        "key_assumptions": {
            "items": [
                {
                    "level": "hard",
                    "triggers_path_fork": False,
                    "description": "TAM > 1B",
                },
                {
                    "level": "soft",
                    "triggers_path_fork": True,
                    "description": "NRR > 120%",
                },
            ]
        }
    }
    result = check_re_001(snapshot)
    assert result is not None
    assert result["evidence"]["rule_id"] == "RE-001"
    assert len(result["evidence"]["mismatched_assumptions"]) == 2


def test_re_001_no_trigger():
    snapshot = {
        "key_assumptions": {
            "items": [
                {"level": "hard", "triggers_path_fork": True, "description": "ok"},
                {"level": "soft", "triggers_path_fork": False, "description": "ok"},
            ]
        }
    }
    assert check_re_001(snapshot) is None


# ── RE-002: 市场有效性-竞争格局矛盾 ──────────────────────────────────────


def test_re_002_triggers():
    snapshot = {
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "high"},
                "competition": {"score": "low"},
            }
        },
        "path_forks": [{"trigger": "hard_assumption_unverified"}],
    }
    result = check_re_002(snapshot)
    assert result is not None
    assert result["evidence"]["rule_id"] == "RE-002"


def test_re_002_no_trigger_has_fork():
    snapshot = {
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "high"},
                "competition": {"score": "low"},
            }
        },
        "path_forks": [{"trigger": "macro_timing_mismatch"}],
    }
    assert check_re_002(snapshot) is None


def test_re_002_no_trigger_scores_dont_match():
    snapshot = {
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "low"},
                "competition": {"score": "low"},
            }
        },
        "path_forks": [],
    }
    assert check_re_002(snapshot) is None


# ── RE-003: Benchmark lens 与 verdict 不一致 ─────────────────────────────


def test_re_003_triggers():
    snapshot = {
        "benchmark_comparison": {"confidence_delta": -0.12},
        "decision": "invest",
    }
    result = check_re_003(snapshot)
    assert result is not None
    assert result["evidence"]["rule_id"] == "RE-003"
    assert result["evidence"]["benchmark_confidence_delta"] == -0.12


def test_re_003_no_trigger_positive_delta():
    snapshot = {
        "benchmark_comparison": {"confidence_delta": 0.05},
        "decision": "invest",
    }
    assert check_re_003(snapshot) is None


def test_re_003_no_trigger_pass_decision():
    snapshot = {
        "benchmark_comparison": {"confidence_delta": -0.12},
        "decision": "pass_for_now",
    }
    assert check_re_003(snapshot) is None


def test_re_003_no_trigger_priority_diligence():
    """priority_diligence is already a downgraded decision — not a false positive."""
    snapshot = {
        "benchmark_comparison": {"confidence_delta": -0.12},
        "decision": "priority_diligence",
    }
    assert check_re_003(snapshot) is None


# ── RE-004: Monitoring trigger 缺失 ─────────────────────────────────────


def test_re_004_triggers():
    snapshot = {
        "decision": "invest",
        "monitoring_triggers": [{"trigger": "only one"}],
    }
    result = check_re_004(snapshot)
    assert result is not None
    assert result["evidence"]["rule_id"] == "RE-004"
    assert result["evidence"]["trigger_count"] == 1


def test_re_004_no_trigger_enough():
    snapshot = {
        "decision": "invest",
        "monitoring_triggers": [{"trigger": "a"}, {"trigger": "b"}],
    }
    assert check_re_004(snapshot) is None


def test_re_004_no_trigger_non_invest():
    snapshot = {
        "decision": "monitor",
        "monitoring_triggers": [],
    }
    assert check_re_004(snapshot) is None


def test_re_004_null_monitoring_triggers():
    """monitoring_triggers: null should not raise TypeError."""
    snapshot = {
        "decision": "invest",
        "monitoring_triggers": None,
    }
    result = check_re_004(snapshot)
    assert result is not None
    assert result["evidence"]["trigger_count"] == 0


# ── RE-005: 跨轮信号震荡 ────────────────────────────────────────────────


def test_re_005_triggers():
    snapshot = {
        "reasoning_trace": {
            "round_traces": [
                {"dimensions": {"tech_barrier": {"score": "high"}}},
                {"dimensions": {"tech_barrier": {"score": "low"}}},
            ]
        }
    }
    result = check_re_005(snapshot)
    assert result is not None
    assert result["evidence"]["rule_id"] == "RE-005"
    assert result["evidence"]["oscillations"][0]["dimension"] == "tech_barrier"


def test_re_005_no_trigger_small_change():
    snapshot = {
        "reasoning_trace": {
            "round_traces": [
                {"dimensions": {"tech_barrier": {"score": "high"}}},
                {"dimensions": {"tech_barrier": {"score": "medium"}}},
            ]
        }
    }
    assert check_re_005(snapshot) is None


def test_re_005_no_trigger_single_round():
    snapshot = {
        "reasoning_trace": {
            "round_traces": [
                {"dimensions": {"tech_barrier": {"score": "high"}}},
            ]
        }
    }
    assert check_re_005(snapshot) is None


# ── RE-006: 置信度与不确定性矛盾 ────────────────────────────────────────


def test_re_006_triggers():
    snapshot = {
        "confidence": 0.95,
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "high"},
                "tech_barrier": {"score": "high"},
                "team_execution": {"score": "low"},
            }
        },
    }
    result = check_re_006(snapshot)
    assert result is not None
    assert result["severity"] == "critical"
    assert result["evidence"]["rule_id"] == "RE-006"
    assert result["evidence"]["high_count"] == 2


def test_re_006_no_trigger_low_confidence():
    snapshot = {
        "confidence": 0.7,
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "high"},
                "tech_barrier": {"score": "high"},
            }
        },
    }
    assert check_re_006(snapshot) is None


def test_re_006_no_trigger_few_high():
    snapshot = {
        "confidence": 0.95,
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "high"},
                "tech_barrier": {"score": "medium"},
            }
        },
    }
    assert check_re_006(snapshot) is None


# ── RE-007: path_forks 数量与 verdict 脱节 ──────────────────────────────


def test_re_007_triggers():
    snapshot = {
        "decision": "invest",
        "confidence": 1.0,
        "path_forks": [
            {"trigger": "hard_assumption_unverified", "trigger_assumption": "a1"},
            {"trigger": "hard_assumption_unverified", "trigger_assumption": "a2"},
            {"trigger": "hard_assumption_unverified", "trigger_assumption": "a3"},
        ],
    }
    result = check_re_007(snapshot)
    assert result is not None
    assert result["evidence"]["rule_id"] == "RE-007"
    assert result["evidence"]["unverified_fork_count"] == 3


def test_re_007_no_trigger_few_forks():
    snapshot = {
        "decision": "invest",
        "confidence": 1.0,
        "path_forks": [
            {"trigger": "hard_assumption_unverified"},
            {"trigger": "hard_assumption_unverified"},
        ],
    }
    assert check_re_007(snapshot) is None


def test_re_007_no_trigger_low_confidence():
    snapshot = {
        "decision": "invest",
        "confidence": 0.8,
        "path_forks": [
            {"trigger": "hard_assumption_unverified"},
            {"trigger": "hard_assumption_unverified"},
            {"trigger": "hard_assumption_unverified"},
        ],
    }
    assert check_re_007(snapshot) is None


# ── Integration: detect_reasoning_errors ─────────────────────────────────


def test_detect_multiple_issues():
    """Snapshot that triggers RE-004, RE-006, and RE-007 simultaneously."""
    snapshot = {
        "decision": "invest",
        "confidence": 0.95,
        "monitoring_triggers": [],
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "high"},
                "tech_barrier": {"score": "high"},
            }
        },
        "path_forks": [
            {"trigger": "hard_assumption_unverified", "trigger_assumption": "a1"},
            {"trigger": "hard_assumption_unverified", "trigger_assumption": "a2"},
            {"trigger": "hard_assumption_unverified", "trigger_assumption": "a3"},
        ],
    }
    issues = detect_reasoning_errors(snapshot)
    rule_ids = {i["evidence"]["rule_id"] for i in issues}
    assert "RE-004" in rule_ids
    assert "RE-006" in rule_ids
    assert "RE-007" in rule_ids
    assert len(issues) >= 3


def test_rule_failure_does_not_block_others():
    """Dispatcher try/except ensures one failing rule does not suppress others."""
    snapshot = {
        "decision": "invest",
        "confidence": 0.95,
        # null monitoring_triggers is now handled by RE-004, but the
        # try/except in detect_reasoning_errors still guards against future crashes
        "monitoring_triggers": None,
        "uncertainty_map": {
            "assessments": {
                "market_validity": {"score": "high"},
                "tech_barrier": {"score": "high"},
            }
        },
    }
    issues = detect_reasoning_errors(snapshot)
    # RE-006 should still fire even though RE-004 crashes
    rule_ids = {i["evidence"]["rule_id"] for i in issues}
    assert "RE-006" in rule_ids

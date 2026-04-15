"""
Feedback generator: maps detected PmIssues to actionable PmFeedback records.

Each rule engine issue (RE-001..RE-007) maps to a feedback with:
- feedback_type (prompt / orchestrator / dataset)
- target_component (specific code path to fix)
- priority (p0 / p1 / p2)
- description (rendered from template + issue evidence)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.pm_feedback import PmFeedback
from app.models.pm_issue import PmIssue

logger = logging.getLogger(__name__)


def _extract_re001(evidence: dict) -> dict:
    return {"mismatched_count": len(evidence.get("mismatched_assumptions", []))}


def _extract_re003(evidence: dict) -> dict:
    return {
        "delta": evidence.get("benchmark_confidence_delta", "N/A"),
        "decision": evidence.get("decision", "N/A"),
    }


def _extract_re004(evidence: dict) -> dict:
    return {"count": evidence.get("trigger_count", 0)}


def _extract_re005(evidence: dict) -> dict:
    oscillations = evidence.get("oscillations", [])
    if not oscillations:
        return {"dim": "N/A", "a": "?", "b": "?", "score_a": "?", "score_b": "?"}
    first = oscillations[0]
    return {
        "dim": first.get("dimension", "N/A"),
        "a": first.get("round_a", "?"),
        "b": first.get("round_b", "?"),
        "score_a": first.get("score_a", "?"),
        "score_b": first.get("score_b", "?"),
    }


def _extract_re006(evidence: dict) -> dict:
    return {
        "conf": evidence.get("confidence", "N/A"),
        "count": evidence.get("high_count", 0),
    }


def _extract_re007(evidence: dict) -> dict:
    return {
        "fork_count": evidence.get("unverified_fork_count", 0),
        "decision": evidence.get("decision", "N/A"),
        "conf": evidence.get("confidence", "N/A"),
    }


ISSUE_TO_FEEDBACK_RULES: dict[str, dict] = {
    "RE-001": {
        "feedback_type": "prompt",
        "target_component": "primary_prompts.ASSUMPTION_SYSTEM_PROMPT",
        "priority": "p1",
        "template": (
            "triggers_path_fork 标注规则未被 LLM 准确执行："
            "{mismatched_count} 个假设的 level 与 triggers_path_fork 不一致"
        ),
        "extractor": _extract_re001,
    },
    "RE-002": {
        "feedback_type": "orchestrator",
        "target_component": "path_fork.PathForkService._check_macro_timing_mismatch",
        "priority": "p1",
        "template": (
            "MACRO_TIMING_MISMATCH 触发条件满足但未生成 fork，"
            "可能因 founder_analysis 缺失导致分支未执行"
        ),
        "extractor": None,
    },
    "RE-003": {
        "feedback_type": "orchestrator",
        "target_component": "primary.PrimaryOrchestrator._resolve_decision",
        "priority": "p0",
        "template": (
            "Benchmark lens confidence_delta={delta} 但仍给出 {decision}，"
            "verdict pipeline 需要更强的 benchmark 门控"
        ),
        "extractor": _extract_re003,
    },
    "RE-004": {
        "feedback_type": "prompt",
        "target_component": "primary_prompts.MONITORING_TRIGGER_PROMPT",
        "priority": "p1",
        "template": (
            "INVEST 决策仅生成 {count} 个 monitoring triggers，"
            "prompt 需强调最低数量要求"
        ),
        "extractor": _extract_re004,
    },
    "RE-005": {
        "feedback_type": "orchestrator",
        "target_component": "primary.PrimaryOrchestrator._run_dimension_agents",
        "priority": "p1",
        "template": (
            "维度 {dim} 在 round {a}→{b} 发生 {score_a}→{score_b} 震荡，"
            "跨轮记忆注入可能不足"
        ),
        "extractor": _extract_re005,
    },
    "RE-006": {
        "feedback_type": "orchestrator",
        "target_component": "primary.PrimaryOrchestrator._resolve_decision",
        "priority": "p0",
        "template": (
            "confidence={conf} 但有 {count} 个 HIGH 不确定性维度，"
            "verdict pipeline 需要多维度 HIGH 惩罚机制"
        ),
        "extractor": _extract_re006,
    },
    "RE-007": {
        "feedback_type": "orchestrator",
        "target_component": "primary.PrimaryOrchestrator._resolve_decision",
        "priority": "p0",
        "template": (
            "{fork_count} 个未验证硬假设 + decision={decision} + confidence={conf}，"
            "verdict 对未验证假设数量不敏感"
        ),
        "extractor": _extract_re007,
    },
}


def _next_version(db: Session) -> int:
    result = db.query(func.max(PmFeedback.feedback_version)).scalar()
    return (result or 0) + 1


def generate_feedback_for_issues(
    case_id: str,
    issues: list[PmIssue],
    db: Session,
) -> list[PmFeedback]:
    """
    Generate PmFeedback records from detected issues.

    - Maps each issue to feedback via ISSUE_TO_FEEDBACK_RULES
    - Dedup: skips if feedback already exists for same case_id + issue_id
    - Uses db.flush() so caller controls the transaction
    """
    version = _next_version(db)
    now = datetime.now(timezone.utc)
    created: list[PmFeedback] = []

    for issue in issues:
        evidence = issue.evidence or {}
        rule_id = evidence.get("rule_id")
        if not rule_id or rule_id not in ISSUE_TO_FEEDBACK_RULES:
            continue

        # Dedup: skip if feedback already exists for this case + issue
        if issue.id:
            exists = (
                db.query(PmFeedback.id)
                .filter(
                    PmFeedback.case_id == case_id,
                    PmFeedback.issue_id == issue.id,
                )
                .first()
            )
            if exists:
                continue

        rule = ISSUE_TO_FEEDBACK_RULES[rule_id]
        extractor = rule.get("extractor")
        template_vars = extractor(evidence) if extractor else {}
        description = rule["template"].format(**template_vars)

        fb = PmFeedback(
            case_id=case_id,
            issue_id=issue.id,
            feedback_type=rule["feedback_type"],
            target_component=rule["target_component"],
            description=description,
            priority=rule["priority"],
            status="open",
            feedback_version=version,
            created_at=now,
        )
        db.add(fb)
        created.append(fb)

    if created:
        db.flush()
        logger.info(
            "case %s: generated %d feedback items (version %d)",
            case_id,
            len(created),
            version,
        )

    return created

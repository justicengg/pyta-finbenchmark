"""
E2E integration test: engine → webhook → detection → feedback.

Constructs payloads that match the actual engine output format
(CompanyAnalysisReport from pyta-research), sends them through the
full finbenchmark pipeline, and verifies issues + feedback are produced.

This covers the critical format conversion path:
  Engine Pydantic → model_dump(mode="json") → webhook → report_snapshot → rule engine
"""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import pm_feedback, pm_webhook
from app.db import Base, get_db
from app.models import PmEvalCase, PmIssue
from app.models.pm_feedback import PmFeedback
from app.services.pm_feedback_generator import generate_feedback_for_issues
from app.services.pm_rule_engine import detect_reasoning_errors


# ── Fixtures ────────────────────────────────────────────────────────


def _build_e2e_app():
    """Build a test app with both webhook and feedback routers."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(pm_webhook.router, prefix="/api")
    app.include_router(pm_feedback.router, prefix="/api/pm")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


# ── Engine-format payload builders ──────────────────────────────────
# These mirror CompanyAnalysisReport.model_dump(mode="json") output


def _engine_payload_triggers_all_rules() -> dict:
    """
    Payload that triggers ALL 7 rules simultaneously.

    Uses engine-native formats:
    - dimension_signals (list) instead of dimensions (dict)
    - hard_assumption_violated (engine enum) instead of hard_assumption_unverified
    - UncertaintyScore string values: "high" / "medium" / "low"
    - PathForkTrigger enum values
    """
    return {
        "event": "primary_run_completed",
        "sandbox_id": f"e2e-all-rules-{uuid.uuid4().hex[:8]}",
        "company_name": "E2E TestCo",
        "sector": "AI Infrastructure",
        "generated_at": "2026-04-15T10:30:00Z",
        # ── Verdict fields (RE-003, RE-004, RE-006, RE-007) ──
        "decision": "invest",
        "confidence": 0.95,
        "decision_rationale": "Strong moat and rapid growth trajectory",
        "overall_verdict": "Invest with conviction despite several unresolved risks",
        # ── Monitoring triggers (RE-004: < 2 triggers) ──
        "monitoring_triggers": [
            {
                "condition": "ARR growth drops below 30% YoY",
                "dimension": "commercialization",
                "action": "re_evaluate",
            }
        ],
        # ── Uncertainty map (RE-002, RE-006) ──
        "uncertainty_map": {
            "market_type": "blue_ocean",
            "assessments": {
                "market_validity": {
                    "score": "high",
                    "narrative": "TAM estimates vary widely",
                    "key_signals": ["No established market benchmarks"],
                },
                "tech_barrier": {
                    "score": "high",
                    "narrative": "Core tech unproven at scale",
                    "key_signals": ["Novel architecture, no production data"],
                },
                "team_execution": {
                    "score": "low",
                    "narrative": "Strong founding team with prior exits",
                    "key_signals": ["2x serial founders"],
                },
                "commercialization": {
                    "score": "medium",
                    "narrative": "Early revenue traction",
                    "key_signals": ["$2M ARR, 3 enterprise pilots"],
                },
                "competition": {
                    "score": "low",
                    "narrative": "No direct competitors in vertical",
                    "key_signals": ["First mover in niche"],
                },
                "burn_cycle": {
                    "score": "medium",
                    "narrative": "18 months runway",
                    "key_signals": ["$5M monthly burn, $90M in bank"],
                },
            },
        },
        # ── Founder analysis ──
        "founder_analysis": {
            "company_stage": "0_to_1",
            "archetype": "technical",
            "founder_market_fit": "medium",
            "execution_signal": "Strong shipping velocity, weekly releases",
            "domain_depth": "Deep ML/systems background, 10+ years",
            "team_building": "medium",
            "self_awareness": "high",
            "stage_fit": "matched",
            "stage_fit_narrative": "Technical founders matched to 0-1 stage",
            "key_risks": ["No prior go-to-market experience"],
            "analysis_confidence": 0.8,
        },
        # ── Key assumptions (RE-001: hard with no fork, soft with fork) ──
        "key_assumptions": {
            "items": [
                {
                    "level": "hard",
                    "description": "TAM exceeds $1B in target vertical",
                    "status": "unverified",
                    "time_horizon_months": 18,
                    "triggers_path_fork": False,  # BUG: should be True for hard
                },
                {
                    "level": "hard",
                    "description": "Core inference engine achieves <10ms latency",
                    "status": "unverified",
                    "time_horizon_months": 6,
                    "triggers_path_fork": True,  # correct
                },
                {
                    "level": "soft",
                    "description": "NRR will exceed 120% by month 12",
                    "status": "unverified",
                    "time_horizon_months": 12,
                    "triggers_path_fork": True,  # BUG: should be False for soft
                },
            ]
        },
        # ── Financial lens ──
        "financial_lens": {
            "arr": 2_000_000,
            "arr_growth_rate": 3.5,
            "arr_growth_narrative": "350% YoY from small base",
            "nrr": 1.25,
            "gross_margin": 0.72,
            "monthly_burn": 5_000_000,
            "ltv_cac_ratio": 2.8,
            "runway_months": 18,
            "valuation_narrative": "Premium for category-creating potential",
            "current_round_size": 50_000_000,
            "current_valuation": 500_000_000,
        },
        # ── Valuation analysis ──
        "valuation_analysis": {
            "ev_revenue_multiple": 250.0,
            "peer_ev_revenue_range": "50x-150x",
            "step_up_from_last_round": 3.0,
            "implied_arr_multiple": 250.0,
            "dilution_this_round_pct": 10.0,
            "post_money_valuation": 500_000_000,
            "moic_base": 3.0,
            "moic_upside": 10.0,
            "irr_base_pct": 25.0,
            "irr_upside_pct": 60.0,
            "valuation_verdict": "rich",
            "narrative": "Valuation is rich but justified by category leadership",
        },
        # ── Benchmark comparison (RE-003: negative delta + invest) ──
        "benchmark_comparison": {
            "peer_count": 5,
            "nrr_vs_peers": "above",
            "gross_margin_vs_peers": "on_par",
            "valuation_vs_peers": "premium",
            "confidence_delta": -0.15,
            "summary_notes": [
                "Valuation significantly above peer median",
                "Growth metrics in top quartile",
            ],
        },
        # ── Investor lens impact ──
        "investor_lens_impact": {
            "verdict_shift": -1,
            "active_blockers": ["Valuation concerns at current round"],
            "active_enablers": ["Category leadership potential"],
            "confidence_delta": -0.05,
            "summary": "Investor lens adds caution on valuation",
        },
        # ── Path forks (RE-002, RE-007: 3+ hard_assumption_violated) ──
        "path_forks": [
            {
                "fork_id": "pf-001",
                "trigger": "hard_assumption_violated",
                "trigger_assumption": "TAM exceeds $1B",
                "scenario_if_holds": "Market large enough for $1B+ outcome",
                "scenario_if_fails": "Niche market caps at $200M outcome",
                "recommended_action": "Commission independent TAM study",
                "deprecated": False,
            },
            {
                "fork_id": "pf-002",
                "trigger": "hard_assumption_violated",
                "trigger_assumption": "Core inference latency <10ms",
                "scenario_if_holds": "Product achieves real-time performance",
                "scenario_if_fails": "Product limited to batch processing",
                "recommended_action": "Review engineering benchmarks",
                "deprecated": False,
            },
            {
                "fork_id": "pf-003",
                "trigger": "hard_assumption_violated",
                "trigger_assumption": "Enterprise adoption rate >20%",
                "scenario_if_holds": "Rapid enterprise expansion",
                "scenario_if_fails": "Slow adoption limits growth",
                "recommended_action": "Analyze pilot conversion funnel",
                "deprecated": False,
            },
        ],
        # ── Reasoning trace (RE-005: oscillation in dimension signals) ──
        "reasoning_trace": {
            "trace_id": "trace-e2e-001",
            "dimension_signals": [
                {
                    "dimension": "market_validity",
                    "score": "high",
                    "key_signals": ["Large addressable market"],
                },
                {
                    "dimension": "tech_barrier",
                    "score": "high",
                    "key_signals": ["Novel approach"],
                },
            ],
            "confidence_path": {
                "raw_avg": 0.78,
                "benchmark_delta": -0.15,
                "investor_delta": -0.05,
                "final": 0.95,
            },
            "verdict_path": {
                "base_score": 0.78,
                "benchmark_shift": -0.15,
                "investor_shift": -0.05,
                "final_score": 0.95,
                "decision": "invest",
            },
            "violated_hard_count": 3,
            "stop_reason": "max_rounds",
            "rounds_completed": 2,
            "round_traces": [
                {
                    "round_number": 1,
                    "avg_confidence": 0.75,
                    "dimension_signals": [
                        {
                            "dimension": "market_validity",
                            "score": "high",
                            "confidence": 0.7,
                        },
                        {
                            "dimension": "tech_barrier",
                            "score": "high",
                            "confidence": 0.6,
                        },
                        {
                            "dimension": "team_execution",
                            "score": "low",
                            "confidence": 0.9,
                        },
                    ],
                },
                {
                    "round_number": 2,
                    "avg_confidence": 0.80,
                    "dimension_signals": [
                        {
                            "dimension": "market_validity",
                            "score": "low",
                            "confidence": 0.8,
                        },
                        {
                            "dimension": "tech_barrier",
                            "score": "high",
                            "confidence": 0.65,
                        },
                        {
                            "dimension": "team_execution",
                            "score": "low",
                            "confidence": 0.95,
                        },
                    ],
                },
            ],
        },
        # ── Metadata ──
        "active_dimensions": [
            "market_validity",
            "tech_barrier",
            "team_execution",
            "commercialization",
            "competition",
            "burn_cycle",
        ],
        "context_summary": {"source_docs": 3, "total_pages": 45},
        "restore_integrity": "full",
        "skipped_dimensions_by_round": {},
        "registry_snapshot": {},
    }


def _engine_payload_clean() -> dict:
    """
    Payload that should NOT trigger any rules.

    Represents a well-formed engine output with no reasoning errors:
    - Hard assumptions correctly flagged with triggers_path_fork=True
    - Soft assumptions with triggers_path_fork=False
    - Low confidence with high uncertainty → consistent
    - Sufficient monitoring triggers
    - No cross-round oscillation
    """
    return {
        "event": "primary_run_completed",
        "sandbox_id": f"e2e-clean-{uuid.uuid4().hex[:8]}",
        "company_name": "CleanCo",
        "sector": "SaaS",
        "generated_at": "2026-04-15T11:00:00Z",
        "decision": "priority_diligence",
        "confidence": 0.72,
        "decision_rationale": "Promising but needs further validation",
        "overall_verdict": "Priority diligence recommended",
        "monitoring_triggers": [
            {
                "condition": "Revenue growth sustains >100% YoY",
                "dimension": "commercialization",
                "action": "upgrade to invest",
            },
            {
                "condition": "Key hire VP Engineering within 3 months",
                "dimension": "team_execution",
                "action": "re_evaluate",
            },
            {
                "condition": "Series B closes at reasonable terms",
                "dimension": "burn_cycle",
                "action": "invest",
            },
        ],
        "uncertainty_map": {
            "market_type": "red_ocean",
            "assessments": {
                "market_validity": {
                    "score": "low",
                    "narrative": "Well-established market",
                    "key_signals": ["Clear TAM data available"],
                },
                "tech_barrier": {
                    "score": "medium",
                    "narrative": "Incremental innovation",
                    "key_signals": ["Faster but not unique"],
                },
                "team_execution": {
                    "score": "low",
                    "narrative": "Experienced team",
                    "key_signals": ["Prior successful exits"],
                },
            },
        },
        "key_assumptions": {
            "items": [
                {
                    "level": "hard",
                    "description": "Enterprise market ready for product",
                    "status": "confirmed",
                    "time_horizon_months": 6,
                    "triggers_path_fork": True,
                },
                {
                    "level": "soft",
                    "description": "Can achieve 90% gross margin at scale",
                    "status": "unverified",
                    "time_horizon_months": 18,
                    "triggers_path_fork": False,
                },
            ]
        },
        "financial_lens": {"arr": 10_000_000, "gross_margin": 0.85},
        "path_forks": [
            {
                "fork_id": "pf-100",
                "trigger": "structural_divergence",
                "trigger_assumption": "Market structure",
                "scenario_if_holds": "Smooth expansion",
                "scenario_if_fails": "Need pivot",
                "recommended_action": "Monitor quarterly",
                "deprecated": False,
            }
        ],
        "reasoning_trace": {
            "trace_id": "trace-clean-001",
            "rounds_completed": 2,
            "round_traces": [
                {
                    "round_number": 1,
                    "avg_confidence": 0.70,
                    "dimension_signals": [
                        {
                            "dimension": "market_validity",
                            "score": "low",
                            "confidence": 0.8,
                        },
                        {
                            "dimension": "tech_barrier",
                            "score": "medium",
                            "confidence": 0.7,
                        },
                    ],
                },
                {
                    "round_number": 2,
                    "avg_confidence": 0.72,
                    "dimension_signals": [
                        {
                            "dimension": "market_validity",
                            "score": "low",
                            "confidence": 0.85,
                        },
                        {
                            "dimension": "tech_barrier",
                            "score": "medium",
                            "confidence": 0.75,
                        },
                    ],
                },
            ],
        },
        "active_dimensions": ["market_validity", "tech_barrier", "team_execution"],
        "context_summary": {},
        "restore_integrity": "full",
        "skipped_dimensions_by_round": {},
        "registry_snapshot": {},
    }


def _engine_payload_partial_triggers() -> dict:
    """
    Payload that triggers only RE-004 (insufficient monitoring triggers)
    and RE-005 (cross-round oscillation).
    All other rules should NOT fire.
    """
    return {
        "event": "primary_run_completed",
        "sandbox_id": f"e2e-partial-{uuid.uuid4().hex[:8]}",
        "company_name": "PartialCo",
        "sector": "Fintech",
        "generated_at": "2026-04-15T12:00:00Z",
        "decision": "invest",
        "confidence": 0.78,  # below 0.8 → RE-006 won't fire; below 0.85 → RE-007 won't fire
        "decision_rationale": "Good fundamentals",
        "overall_verdict": "Invest at current valuation",
        "monitoring_triggers": [],  # RE-004: invest with 0 triggers
        "uncertainty_map": {
            "market_type": "blue_ocean",
            "assessments": {
                "market_validity": {
                    "score": "low",
                    "narrative": "Proven market",
                    "key_signals": [],
                },
                "competition": {
                    "score": "medium",
                    "narrative": "Some competition",
                    "key_signals": [],
                },
            },
        },
        "key_assumptions": {
            "items": [
                {
                    "level": "hard",
                    "description": "Regulatory approval on track",
                    "status": "confirmed",
                    "time_horizon_months": 12,
                    "triggers_path_fork": True,
                },
            ]
        },
        "financial_lens": {"arr": 5_000_000},
        "benchmark_comparison": {
            "peer_count": 3,
            "confidence_delta": 0.02,  # positive → RE-003 won't fire
        },
        "path_forks": [],  # no hard_assumption_violated → RE-007 won't fire
        "reasoning_trace": {
            "trace_id": "trace-partial-001",
            "rounds_completed": 2,
            "round_traces": [
                {
                    "round_number": 1,
                    "avg_confidence": 0.7,
                    "dimension_signals": [
                        {
                            "dimension": "competition",
                            "score": "high",
                            "confidence": 0.6,
                        },
                    ],
                },
                {
                    "round_number": 2,
                    "avg_confidence": 0.75,
                    "dimension_signals": [
                        {
                            "dimension": "competition",
                            "score": "low",  # RE-005: high→low = oscillation
                            "confidence": 0.8,
                        },
                    ],
                },
            ],
        },
        "active_dimensions": ["market_validity", "competition"],
        "context_summary": {},
        "restore_integrity": "full",
        "skipped_dimensions_by_round": {},
        "registry_snapshot": {},
    }


# ── Test: Rule engine on engine-format snapshots (pure logic) ───────


class TestRuleEngineWithEngineFormat:
    """Rule engine fires correctly on engine-native payload formats."""

    def test_all_rules_fire(self):
        """Payload designed to trigger all 7 rules fires them all."""
        payload = _engine_payload_triggers_all_rules()
        issues = detect_reasoning_errors(payload)
        rule_ids = {i["evidence"]["rule_id"] for i in issues}

        assert "RE-001" in rule_ids, "RE-001 (assumption-fork mismatch) should fire"
        assert "RE-002" in rule_ids, (
            "RE-002 (market-competition contradiction) should fire"
        )
        assert "RE-003" in rule_ids, "RE-003 (benchmark vs verdict) should fire"
        assert "RE-004" in rule_ids, (
            "RE-004 (insufficient monitoring triggers) should fire"
        )
        assert "RE-005" in rule_ids, "RE-005 (cross-round oscillation) should fire"
        assert "RE-006" in rule_ids, (
            "RE-006 (confidence-uncertainty mismatch) should fire"
        )
        assert "RE-007" in rule_ids, "RE-007 (path forks vs verdict) should fire"
        assert len(issues) == 7

    def test_clean_payload_no_issues(self):
        """Well-formed engine payload triggers zero rules."""
        payload = _engine_payload_clean()
        issues = detect_reasoning_errors(payload)
        assert issues == [], (
            f"Expected no issues, got: {[i['evidence']['rule_id'] for i in issues]}"
        )

    def test_partial_triggers(self):
        """Payload that should trigger only RE-004 and RE-005."""
        payload = _engine_payload_partial_triggers()
        issues = detect_reasoning_errors(payload)
        rule_ids = {i["evidence"]["rule_id"] for i in issues}

        assert rule_ids == {"RE-004", "RE-005"}, (
            f"Expected RE-004+RE-005, got: {rule_ids}"
        )

    def test_issue_structure_integrity(self):
        """Every detected issue has required fields for PmIssue model."""
        payload = _engine_payload_triggers_all_rules()
        issues = detect_reasoning_errors(payload)

        required_keys = {
            "issue_type",
            "severity",
            "stage",
            "dimension",
            "expected",
            "actual",
            "evidence",
            "root_cause_hint",
            "action_suggestion",
            "attribution_hint",
            "detected_by",
        }
        for issue in issues:
            missing = required_keys - set(issue.keys())
            assert not missing, (
                f"Rule {issue['evidence']['rule_id']} missing keys: {missing}"
            )

    def test_re005_engine_dimension_signals_format(self):
        """RE-005 correctly processes engine's dimension_signals list format."""
        payload = _engine_payload_triggers_all_rules()
        issues = detect_reasoning_errors(payload)
        re005 = [i for i in issues if i["evidence"]["rule_id"] == "RE-005"]
        assert len(re005) == 1

        oscillations = re005[0]["evidence"]["oscillations"]
        assert len(oscillations) >= 1
        osc = oscillations[0]
        assert osc["dimension"] == "market_validity"
        assert osc["score_a"] == "high"
        assert osc["score_b"] == "low"
        assert osc["round_a"] == 1
        assert osc["round_b"] == 2

    def test_re007_engine_trigger_enum_value(self):
        """RE-007 correctly matches engine's 'hard_assumption_violated' trigger."""
        payload = _engine_payload_triggers_all_rules()
        issues = detect_reasoning_errors(payload)
        re007 = [i for i in issues if i["evidence"]["rule_id"] == "RE-007"]
        assert len(re007) == 1
        assert re007[0]["evidence"]["unverified_fork_count"] == 3

    def test_re002_no_macro_fork_fires(self):
        """RE-002: market=high, competition=low, no macro_timing_mismatch fork → fires."""
        payload = _engine_payload_triggers_all_rules()
        issues = detect_reasoning_errors(payload)
        re002 = [i for i in issues if i["evidence"]["rule_id"] == "RE-002"]
        assert len(re002) == 1
        assert re002[0]["evidence"]["market_validity_score"] == "high"
        assert re002[0]["evidence"]["competition_score"] == "low"


# ── Test: Webhook accepts engine-format payloads ────────────────────


class TestWebhookAcceptsEngineFormat:
    """Webhook endpoint correctly ingests engine-native payloads."""

    def test_webhook_accepts_full_engine_payload(self):
        client, _ = _build_e2e_app()
        payload = _engine_payload_triggers_all_rules()
        resp = client.post("/api/webhook/primary-run-completed", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert "case_id" in body

    def test_webhook_accepts_clean_payload(self):
        client, _ = _build_e2e_app()
        payload = _engine_payload_clean()
        resp = client.post("/api/webhook/primary-run-completed", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_webhook_stores_complete_snapshot(self):
        """report_snapshot preserves all engine fields needed by rule engine."""
        client, DBSession = _build_e2e_app()
        payload = _engine_payload_triggers_all_rules()
        resp = client.post("/api/webhook/primary-run-completed", json=payload)
        case_id = resp.json()["case_id"]

        with DBSession() as db:
            case = db.query(PmEvalCase).filter(PmEvalCase.id == case_id).first()
            snapshot = case.report_snapshot

        # Verify critical fields are preserved in snapshot
        assert snapshot["decision"] == "invest"
        assert snapshot["confidence"] == 0.95

        # Verify nested structures survived serialization
        assert "assessments" in snapshot["uncertainty_map"]
        assert (
            snapshot["uncertainty_map"]["assessments"]["market_validity"]["score"]
            == "high"
        )

        # Verify engine-format fields are preserved
        round_traces = snapshot["reasoning_trace"]["round_traces"]
        assert len(round_traces) == 2
        assert "dimension_signals" in round_traces[0]
        assert round_traces[0]["dimension_signals"][0]["dimension"] == "market_validity"

        # Verify path forks with engine trigger values
        assert len(snapshot["path_forks"]) == 3
        assert snapshot["path_forks"][0]["trigger"] == "hard_assumption_violated"

        # Verify key_assumptions structure
        items = snapshot["key_assumptions"]["items"]
        assert len(items) == 3
        assert items[0]["level"] == "hard"
        assert items[0]["triggers_path_fork"] is False

        # Verify benchmark_comparison
        assert snapshot["benchmark_comparison"]["confidence_delta"] == -0.15


# ── Test: Full pipeline (webhook → detect → feedback) ──────────────


class TestFullPipeline:
    """End-to-end: webhook ingestion → rule engine detection → feedback generation."""

    def _ingest_and_detect(self, payload: dict):
        """Send payload through webhook, then run detection + feedback."""
        client, DBSession = _build_e2e_app()

        # Step 1: Ingest via webhook
        resp = client.post("/api/webhook/primary-run-completed", json=payload)
        assert resp.status_code == 200
        case_id = resp.json()["case_id"]

        # Step 2: Run detection (simulates pm_detect job)
        with DBSession() as db:
            case = db.query(PmEvalCase).filter(PmEvalCase.id == case_id).first()
            snapshot = case.report_snapshot
            assert snapshot is not None

            issues = detect_reasoning_errors(snapshot)
            now = datetime.now(timezone.utc)

            for issue_dict in issues:
                issue = PmIssue(
                    case_id=case.id,
                    detected_at=now,
                    **issue_dict,
                )
                db.add(issue)

            db.flush()

            # Step 3: Generate feedback
            pm_issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()
            generate_feedback_for_issues(case.id, pm_issues, db)

            case.status = "detected"
            db.commit()

            # Re-query for assertions (avoid detached instance)
            final_issues = db.query(PmIssue).filter(PmIssue.case_id == case_id).all()
            final_feedbacks = (
                db.query(PmFeedback).filter(PmFeedback.case_id == case_id).all()
            )

            issue_data = [
                {"rule_id": i.evidence["rule_id"], "severity": i.severity}
                for i in final_issues
            ]
            feedback_data = [
                {
                    "rule_id": f.description,
                    "feedback_type": f.feedback_type,
                    "target_component": f.target_component,
                    "priority": f.priority,
                    "status": f.status,
                }
                for f in final_feedbacks
            ]
            case_status = case.status

        return {
            "case_id": case_id,
            "case_status": case_status,
            "issues": issue_data,
            "feedbacks": feedback_data,
            "issue_count": len(issue_data),
            "feedback_count": len(feedback_data),
        }

    def test_full_pipeline_all_rules(self):
        """All 7 rules detected → 7 issues → 7 feedback items."""
        result = self._ingest_and_detect(_engine_payload_triggers_all_rules())

        assert result["case_status"] == "detected"
        assert result["issue_count"] == 7
        assert result["feedback_count"] == 7

        rule_ids = {i["rule_id"] for i in result["issues"]}
        assert rule_ids == {
            "RE-001",
            "RE-002",
            "RE-003",
            "RE-004",
            "RE-005",
            "RE-006",
            "RE-007",
        }

    def test_full_pipeline_clean_payload(self):
        """Clean payload → 0 issues → 0 feedback items."""
        result = self._ingest_and_detect(_engine_payload_clean())

        assert result["case_status"] == "detected"
        assert result["issue_count"] == 0
        assert result["feedback_count"] == 0

    def test_full_pipeline_partial_triggers(self):
        """Partial payload → only RE-004 + RE-005 → 2 feedbacks."""
        result = self._ingest_and_detect(_engine_payload_partial_triggers())

        assert result["case_status"] == "detected"
        assert result["issue_count"] == 2
        assert result["feedback_count"] == 2

        rule_ids = {i["rule_id"] for i in result["issues"]}
        assert rule_ids == {"RE-004", "RE-005"}

    def test_feedback_types_match_rules(self):
        """Feedback types align with ISSUE_TO_FEEDBACK_RULES mapping."""
        result = self._ingest_and_detect(_engine_payload_triggers_all_rules())

        feedbacks = result["feedbacks"]
        prompt_feedbacks = [f for f in feedbacks if f["feedback_type"] == "prompt"]
        orchestrator_feedbacks = [
            f for f in feedbacks if f["feedback_type"] == "orchestrator"
        ]

        # RE-001, RE-004 → prompt; RE-002, RE-003, RE-005, RE-006, RE-007 → orchestrator
        assert len(prompt_feedbacks) == 2
        assert len(orchestrator_feedbacks) == 5

    def test_feedback_priorities(self):
        """Critical rules get p0 priority, others get p1."""
        result = self._ingest_and_detect(_engine_payload_triggers_all_rules())

        feedbacks = result["feedbacks"]
        p0_feedbacks = [f for f in feedbacks if f["priority"] == "p0"]
        p1_feedbacks = [f for f in feedbacks if f["priority"] == "p1"]

        # RE-003, RE-006, RE-007 → p0; RE-001, RE-002, RE-004, RE-005 → p1
        assert len(p0_feedbacks) == 3
        assert len(p1_feedbacks) == 4

    def test_all_feedbacks_start_open(self):
        """All generated feedback records start with status=open."""
        result = self._ingest_and_detect(_engine_payload_triggers_all_rules())
        for fb in result["feedbacks"]:
            assert fb["status"] == "open"


# ── Test: Feedback API with engine-format data ──────────────────────


class TestFeedbackAPIWithEngineData:
    """Feedback API returns correct data after full pipeline processing."""

    def _setup_pipeline(self):
        """Run full pipeline and return (client, case_id)."""
        client, DBSession = _build_e2e_app()
        payload = _engine_payload_triggers_all_rules()
        resp = client.post("/api/webhook/primary-run-completed", json=payload)
        case_id = resp.json()["case_id"]

        with DBSession() as db:
            case = db.query(PmEvalCase).filter(PmEvalCase.id == case_id).first()
            snapshot = case.report_snapshot
            issues = detect_reasoning_errors(snapshot)
            now = datetime.now(timezone.utc)

            for issue_dict in issues:
                db.add(PmIssue(case_id=case.id, detected_at=now, **issue_dict))
            db.flush()

            pm_issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()
            generate_feedback_for_issues(case.id, pm_issues, db)
            case.status = "detected"
            db.commit()

        return client, case_id

    def test_list_feedback_by_case(self):
        client, case_id = self._setup_pipeline()
        resp = client.get(f"/api/pm/feedback/?case_id={case_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 7
        assert len(body["items"]) == 7

    def test_list_feedback_filter_by_type(self):
        client, case_id = self._setup_pipeline()

        resp = client.get(f"/api/pm/feedback/?case_id={case_id}&feedback_type=prompt")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        for item in body["items"]:
            assert item["feedback_type"] == "prompt"

    def test_list_feedback_filter_by_priority(self):
        client, case_id = self._setup_pipeline()

        resp = client.get(f"/api/pm/feedback/?case_id={case_id}&priority=p0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        for item in body["items"]:
            assert item["priority"] == "p0"

    def test_patch_feedback_status(self):
        client, case_id = self._setup_pipeline()

        # Get first feedback
        resp = client.get(f"/api/pm/feedback/?case_id={case_id}&limit=1")
        fb_id = resp.json()["items"][0]["id"]

        # Patch to resolved
        resp = client.patch(f"/api/pm/feedback/{fb_id}", json={"status": "resolved"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["resolved_at"] is not None

        # Patch back to open (resolved_at should clear)
        resp = client.patch(f"/api/pm/feedback/{fb_id}", json={"status": "open"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "open"
        assert body["resolved_at"] is None

    def test_feedback_summary(self):
        client, _ = self._setup_pipeline()

        resp = client.get("/api/pm/feedback/summary")
        assert resp.status_code == 200
        body = resp.json()

        # Should have both prompt and orchestrator types
        assert "prompt" in body
        assert "orchestrator" in body

    def test_feedback_descriptions_rendered(self):
        """Feedback descriptions contain actual evidence values, not template vars."""
        client, case_id = self._setup_pipeline()

        resp = client.get(f"/api/pm/feedback/?case_id={case_id}")
        items = resp.json()["items"]

        for item in items:
            desc = item["description"]
            # No unrendered template variables
            assert "{" not in desc, f"Unrendered template in: {desc}"
            assert "}" not in desc, f"Unrendered template in: {desc}"
            # Should contain actual Chinese text (our templates are in Chinese)
            assert len(desc) > 10, f"Description too short: {desc}"


# ── Test: Idempotency & dedup across pipeline ──────────────────────


class TestPipelineIdempotency:
    """Running detection twice produces no duplicates."""

    def test_detection_idempotent(self):
        """Running feedback generation twice on same issues → no duplicate feedback."""
        _, DBSession = _build_e2e_app()
        payload = _engine_payload_triggers_all_rules()

        with DBSession() as db:
            # Create case manually
            case = PmEvalCase(
                id=str(uuid.uuid4()),
                sandbox_id=payload["sandbox_id"],
                company_name=payload["company_name"],
                sector=payload["sector"],
                run_timestamp=datetime.now(timezone.utc),
                decision=payload["decision"],
                confidence=payload["confidence"],
                report_snapshot=payload,
                status="pending",
                source="online",
            )
            db.add(case)
            db.flush()

            # First detection round
            issues = detect_reasoning_errors(payload)
            now = datetime.now(timezone.utc)
            for issue_dict in issues:
                db.add(PmIssue(case_id=case.id, detected_at=now, **issue_dict))
            db.flush()

            pm_issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()
            fb1 = generate_feedback_for_issues(case.id, pm_issues, db)
            db.flush()

            # Second detection round (same issues, should dedup)
            fb2 = generate_feedback_for_issues(case.id, pm_issues, db)
            db.commit()

            total_fb = (
                db.query(PmFeedback).filter(PmFeedback.case_id == case.id).count()
            )

        assert len(fb1) == 7
        assert len(fb2) == 0  # dedup prevents duplicates
        assert total_fb == 7

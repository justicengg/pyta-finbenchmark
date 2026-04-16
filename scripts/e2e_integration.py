#!/usr/bin/env python3
"""
E2E 链路测试脚本：pyta-research 引擎 → pyta-finbenchmark 检测 → 反馈生成

用法：

  ┌──────────────────────────────────────────────────────────────────────┐
  │ 模式 A：全自动（引擎 + finbenchmark 都在运行）                       │
  │   python scripts/e2e_integration.py --engine-url http://localhost:8000 │
  │                                     --eval-url http://localhost:8001   │
  │                                     --company "Cursor (Anysphere)"     │
  │                                     --sector "AI Developer Tools"      │
  ├──────────────────────────────────────────────────────────────────────┤
  │ 模式 B：只测 finbenchmark（用模拟 payload）                          │
  │   python scripts/e2e_integration.py --eval-url http://localhost:8001   │
  │                                     --mock                             │
  ├──────────────────────────────────────────────────────────────────────┤
  │ 模式 C：从引擎 API 响应文件加载                                      │
  │   python scripts/e2e_integration.py --eval-url http://localhost:8001   │
  │                                     --from-file engine_output.json     │
  └──────────────────────────────────────────────────────────────────────┘

前置条件：
  - 模式 A：pyta-research 运行在 --engine-url（默认 :8000）
  - 模式 A/B/C：pyta-finbenchmark 运行在 --eval-url（默认 :8001）

启动服务：
  # Terminal 1: 引擎
  cd ~/Desktop/pyta-research && uvicorn src.api.main:app --port 8000

  # Terminal 2: finbenchmark
  cd ~/Desktop/pyta-research-worktrees/pyta-finbenchmark && uvicorn app.main:app --port 8001
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ── Colors for terminal output ──────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}→{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def header(msg: str) -> None:
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}{msg}{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")


# ── Step 1: Get engine output ───────────────────────────────────────


def run_engine(engine_url: str, company: str, sector: str | None) -> dict:
    """Call engine's /primary/run API and return the report."""
    header("Step 1: Running engine analysis")
    info(f"Engine: {engine_url}")
    info(f"Company: {company}, Sector: {sector or '(auto)'}")

    body = {
        "company_name": company,
        "sector": sector,
        "company_info": {},
        "max_rounds": 2,
    }

    with httpx.Client(timeout=300.0) as client:
        info("Calling POST /primary/run (this may take 1-3 minutes)...")
        t0 = time.time()
        resp = client.post(
            f"{engine_url}/primary/run",
            json=body,
            headers={"X-API-Key": "dev"},
        )
        elapsed = time.time() - t0

    if resp.status_code != 200:
        fail(f"Engine returned {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)

    result = resp.json()
    ok(f"Engine completed in {elapsed:.1f}s")
    info(f"Sandbox ID: {result.get('sandbox_id')}")
    info(f"Rounds completed: {result.get('rounds_completed')}")

    report = result.get("report", {})
    info(f"Decision: {report.get('decision')}, Confidence: {report.get('confidence')}")
    return report


def load_from_file(path: str) -> dict:
    """Load engine output from a JSON file."""
    header("Step 1: Loading engine output from file")
    info(f"File: {path}")

    data = json.loads(Path(path).read_text())

    # Support both raw report and full API response
    if "report" in data:
        report = data["report"]
    else:
        report = data

    ok(f"Loaded report for: {report.get('company_name', '?')}")
    info(f"Decision: {report.get('decision')}, Confidence: {report.get('confidence')}")
    return report


def build_mock_payload() -> dict:
    """Build a mock engine-format payload that triggers multiple rules."""
    header("Step 1: Building mock engine payload")

    payload = {
        "sandbox_id": str(uuid.uuid4()),
        "company_name": "MockCo E2E Test",
        "sector": "AI Infrastructure",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "invest",
        "confidence": 0.95,
        "decision_rationale": "Strong moat and rapid growth",
        "overall_verdict": "Invest with conviction despite risks",
        "monitoring_triggers": [
            {
                "condition": "ARR growth drops below 30%",
                "dimension": "commercialization",
                "action": "re_evaluate",
            }
        ],
        "uncertainty_map": {
            "market_type": "blue_ocean",
            "assessments": {
                "market_validity": {
                    "score": "high",
                    "narrative": "TAM estimates vary widely",
                    "key_signals": ["No established benchmarks"],
                },
                "tech_barrier": {
                    "score": "high",
                    "narrative": "Core tech unproven at scale",
                    "key_signals": ["Novel architecture"],
                },
                "team_execution": {
                    "score": "low",
                    "narrative": "Strong founding team",
                    "key_signals": ["2x serial founders"],
                },
                "commercialization": {
                    "score": "medium",
                    "narrative": "Early revenue traction",
                    "key_signals": ["$2M ARR"],
                },
                "competition": {
                    "score": "low",
                    "narrative": "No direct competitors",
                    "key_signals": ["First mover"],
                },
                "burn_cycle": {
                    "score": "medium",
                    "narrative": "18 months runway",
                    "key_signals": ["$5M/mo burn"],
                },
            },
        },
        "founder_analysis": {
            "company_stage": "0_to_1",
            "archetype": "technical",
            "founder_market_fit": "medium",
        },
        "key_assumptions": {
            "items": [
                {
                    "level": "hard",
                    "description": "TAM exceeds $1B",
                    "status": "unverified",
                    "time_horizon_months": 18,
                    "triggers_path_fork": False,  # BUG: hard → should be True
                },
                {
                    "level": "soft",
                    "description": "NRR > 120%",
                    "status": "unverified",
                    "time_horizon_months": 12,
                    "triggers_path_fork": True,  # BUG: soft → should be False
                },
            ]
        },
        "financial_lens": {
            "arr": 2_000_000,
            "gross_margin": 0.72,
            "monthly_burn": 5_000_000,
        },
        "benchmark_comparison": {
            "peer_count": 5,
            "confidence_delta": -0.15,
            "summary_notes": ["Valuation above peer median"],
        },
        "path_forks": [
            {
                "fork_id": f"pf-{i}",
                "trigger": "hard_assumption_violated",
                "trigger_assumption": f"Assumption #{i}",
                "scenario_if_holds": "Positive outcome",
                "scenario_if_fails": "Negative outcome",
                "recommended_action": "Investigate further",
                "deprecated": False,
            }
            for i in range(1, 4)
        ],
        "reasoning_trace": {
            "trace_id": "trace-mock-001",
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
                    ],
                },
            ],
        },
        "active_dimensions": [
            "market_validity",
            "tech_barrier",
            "team_execution",
            "commercialization",
            "competition",
            "burn_cycle",
        ],
        "context_summary": {},
        "restore_integrity": "full",
        "skipped_dimensions_by_round": {},
        "registry_snapshot": {},
    }

    ok("Mock payload built (triggers RE-001 through RE-007)")
    info(f"Sandbox ID: {payload['sandbox_id']}")
    return payload


# ── Step 2: Transform engine report → webhook payload ───────────────


def transform_report_to_webhook_payload(report: dict) -> dict:
    """
    Transform engine CompanyAnalysisReport → finbenchmark webhook payload.

    The webhook (PrimaryRunCompletedPayload) expects:
    - "event": "primary_run_completed" (added)
    - sandbox_id as string
    - All report fields (most pass through as-is)
    - Drops: company_profile, context_narrative, round_id, trace_id
      (webhook doesn't accept these)
    """
    header("Step 2: Transforming report → webhook payload")

    payload = {
        "event": "primary_run_completed",
        "sandbox_id": str(report.get("sandbox_id", uuid.uuid4())),
        "company_name": report.get("company_name", "Unknown"),
        "sector": report.get("sector"),
        "generated_at": report.get(
            "generated_at", datetime.now(timezone.utc).isoformat()
        ),
        "decision": report.get("decision", "monitor"),
        "confidence": report.get("confidence", 0.0),
        "decision_rationale": report.get("decision_rationale", ""),
        "overall_verdict": report.get("overall_verdict", ""),
        "monitoring_triggers": report.get("monitoring_triggers", []),
        "uncertainty_map": report.get("uncertainty_map", {}),
        "founder_analysis": report.get("founder_analysis", {}),
        "key_assumptions": report.get("key_assumptions", {}),
        "financial_lens": report.get("financial_lens", {}),
        "competitive_landscape": report.get("competitive_landscape"),
        "market_sizing": report.get("market_sizing"),
        "valuation_analysis": report.get("valuation_analysis"),
        "benchmark_comparison": report.get("benchmark_comparison"),
        "investor_lens_impact": report.get("investor_lens_impact"),
        "reasoning_trace": report.get("reasoning_trace"),
        "path_forks": report.get("path_forks", []),
        "context_summary": report.get("context_summary", {}),
        "active_dimensions": report.get("active_dimensions", []),
        "restore_integrity": report.get("restore_integrity", "full"),
        "skipped_dimensions_by_round": report.get("skipped_dimensions_by_round", {}),
        "registry_snapshot": report.get("registry_snapshot", {}),
    }

    # Fields dropped (not in webhook schema):
    dropped = [
        f
        for f in ("company_profile", "context_narrative", "round_id", "trace_id")
        if f in report
    ]
    if dropped:
        warn(f"Dropped fields not in webhook schema: {dropped}")

    ok("Webhook payload ready")
    info(f"Payload keys: {len(payload)}")
    return payload


# ── Step 3: Send to finbenchmark ────────────────────────────────────


def send_to_finbenchmark(eval_url: str, payload: dict, secret: str = "") -> str:
    """POST webhook payload to finbenchmark, return case_id."""
    header("Step 3: Sending to finbenchmark webhook")
    info(f"Target: {eval_url}/api/webhook/primary-run-completed")

    headers = {}
    if secret:
        headers["X-Webhook-Secret"] = secret

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{eval_url}/api/webhook/primary-run-completed",
            json=payload,
            headers=headers,
        )

    if resp.status_code != 200:
        fail(f"Webhook returned {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)

    body = resp.json()
    case_id = body["case_id"]

    if body["status"] == "created":
        ok(f"Case created: {case_id}")
    else:
        warn(f"Case already exists: {case_id}")

    return case_id


# ── Step 4: Trigger detection ───────────────────────────────────────


def trigger_detection(eval_url: str, case_id: str) -> None:
    """Trigger the detection job via API (or direct call)."""
    header("Step 4: Triggering detection + feedback generation")
    info(f"Case ID: {case_id}")

    # Try the detect API endpoint if it exists
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{eval_url}/api/pm/detect/run",
        )

    if resp.status_code == 200:
        body = resp.json()
        ok(f"Detection completed: processed {body.get('processed', '?')} cases")
    elif resp.status_code == 404:
        warn("Detection endpoint not found — run manually:")
        warn("  python -c 'from app.jobs.pm_detect import run; run()'")
    else:
        fail(f"Detection returned {resp.status_code}: {resp.text[:300]}")


# ── Step 5: Check results ──────────────────────────────────────────


def check_results(eval_url: str, case_id: str) -> dict:
    """Query issues and feedback for the case."""
    header("Step 5: Checking detection results")

    with httpx.Client(timeout=30.0) as client:
        # Check issues
        issues_resp = client.get(
            f"{eval_url}/api/pm/issues/",
            params={"case_id": case_id, "limit": 50},
        )
        # Check feedback
        feedback_resp = client.get(
            f"{eval_url}/api/pm/feedback/",
            params={"case_id": case_id, "limit": 50},
        )

    results = {"issues": [], "feedbacks": []}

    if issues_resp.status_code == 200:
        issues_body = issues_resp.json()
        issues = issues_body.get("items", [])
        results["issues"] = issues
        ok(f"Detected {len(issues)} issues")

        for issue in issues:
            evidence = issue.get("evidence", {})
            rule_id = evidence.get("rule_id", "?")
            severity = issue.get("severity", "?")
            stage = issue.get("stage", "?")
            info(f"  {rule_id} [{severity}] stage={stage}")
    else:
        warn(f"Issues API returned {issues_resp.status_code}")

    if feedback_resp.status_code == 200:
        fb_body = feedback_resp.json()
        feedbacks = fb_body.get("items", [])
        results["feedbacks"] = feedbacks
        ok(f"Generated {len(feedbacks)} feedback items")

        for fb in feedbacks:
            fb_type = fb.get("feedback_type", "?")
            target = fb.get("target_component", "?")
            priority = fb.get("priority", "?")
            desc = fb.get("description", "")[:80]
            info(f"  [{priority}] {fb_type} → {target}")
            info(f"       {desc}...")
    else:
        warn(f"Feedback API returned {feedback_resp.status_code}")

    return results


# ── Step 6: Summary ────────────────────────────────────────────────


def print_summary(results: dict, payload: dict) -> None:
    """Print a summary of the E2E test results."""
    header("E2E Summary")

    issues = results.get("issues", [])
    feedbacks = results.get("feedbacks", [])

    print(f"""
  Company:   {payload.get("company_name", "?")}
  Decision:  {payload.get("decision", "?")}
  Confidence: {payload.get("confidence", "?")}

  Issues detected:    {len(issues)}
  Feedback generated: {len(feedbacks)}
""")

    if issues:
        rule_ids = sorted({i.get("evidence", {}).get("rule_id", "?") for i in issues})
        print(f"  Rules triggered: {', '.join(rule_ids)}")

        # Group feedback by type
        by_type: dict[str, int] = {}
        for fb in feedbacks:
            t = fb.get("feedback_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        if by_type:
            print(f"  Feedback breakdown: {by_type}")

        # Group by priority
        by_prio: dict[str, int] = {}
        for fb in feedbacks:
            p = fb.get("priority", "?")
            by_prio[p] = by_prio.get(p, 0) + 1
        if by_prio:
            print(f"  Priority breakdown: {by_prio}")

    if len(issues) == 0:
        ok("No reasoning errors detected — engine output is consistent")
    elif len(feedbacks) == len(issues):
        ok("Every issue has a corresponding feedback item")
    else:
        warn(
            f"Issue/feedback count mismatch: {len(issues)} issues vs {len(feedbacks)} feedbacks"
        )

    print()


# ── Main ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="E2E integration test: engine → finbenchmark → feedback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Mock mode (no engine needed):
  python scripts/e2e_integration.py --mock

  # Full pipeline with running engine:
  python scripts/e2e_integration.py --company "Cursor (Anysphere)" --sector "AI Dev Tools"

  # From saved engine output:
  python scripts/e2e_integration.py --from-file output.json
        """,
    )
    parser.add_argument(
        "--engine-url",
        default="http://localhost:8000",
        help="Engine API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--eval-url",
        default="http://localhost:8001",
        help="Finbenchmark API base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--company",
        default="Cursor (Anysphere)",
        help="Company name for engine analysis",
    )
    parser.add_argument("--sector", default=None, help="Sector for engine analysis")
    parser.add_argument(
        "--mock", action="store_true", help="Use mock payload instead of calling engine"
    )
    parser.add_argument(
        "--from-file", default=None, help="Load engine output from JSON file"
    )
    parser.add_argument(
        "--webhook-secret", default="", help="Webhook secret for finbenchmark"
    )
    parser.add_argument(
        "--save-payload",
        default=None,
        help="Save webhook payload to JSON file (for debugging)",
    )
    parser.add_argument(
        "--skip-detect",
        action="store_true",
        help="Skip detection trigger (if already detected)",
    )

    args = parser.parse_args()

    print(f"\n{BOLD}E2E Integration Test: Engine → Finbenchmark → Feedback{RESET}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    # Step 1: Get engine output
    if args.mock:
        payload = build_mock_payload()
    elif args.from_file:
        report = load_from_file(args.from_file)
        payload = transform_report_to_webhook_payload(report)
    else:
        report = run_engine(args.engine_url, args.company, args.sector)
        payload = transform_report_to_webhook_payload(report)

    # Save payload if requested
    if args.save_payload:
        Path(args.save_payload).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False)
        )
        info(f"Payload saved to {args.save_payload}")

    # Step 3: Send to finbenchmark
    case_id = send_to_finbenchmark(args.eval_url, payload, args.webhook_secret)

    # Step 4: Trigger detection
    if not args.skip_detect:
        trigger_detection(args.eval_url, case_id)
    else:
        warn("Skipping detection (--skip-detect)")

    # Step 5: Check results
    results = check_results(args.eval_url, case_id)

    # Step 6: Summary
    print_summary(results, payload)


if __name__ == "__main__":
    main()

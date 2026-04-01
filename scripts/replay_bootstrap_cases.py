"""
Replay bootstrap eval cases through the main sandbox backend and backfill agent snapshots.

Usage:
    cd eval-service
    PYTHONPATH=. .venv/bin/python scripts/replay_bootstrap_cases.py --limit 3

Environment variables:
    EVAL_SERVICE_URL       default http://127.0.0.1:8001
    MAIN_BACKEND_URL       default http://127.0.0.1:8000
    MAIN_BACKEND_API_KEY   optional; sent as X-API-Key when present
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from typing import Any

import httpx

EVAL_SERVICE_URL = os.environ.get("EVAL_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
MAIN_BACKEND_URL = os.environ.get("MAIN_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
MAIN_BACKEND_API_KEY = os.environ.get("MAIN_BACKEND_API_KEY", "")


def build_client() -> httpx.Client:
    return httpx.Client(timeout=120.0)


def fetch_bootstrap_cases(client: httpx.Client, limit: int) -> list[dict[str, Any]]:
    response = client.get(
        f"{EVAL_SERVICE_URL}/api/cases/",
        params={"source": "bootstrap", "limit": limit, "offset": 0},
    )
    response.raise_for_status()
    items = response.json()["items"]
    cases: list[dict[str, Any]] = []
    for item in items:
        detail_response = client.get(f"{EVAL_SERVICE_URL}/api/cases/{item['id']}")
        detail_response.raise_for_status()
        cases.append(detail_response.json())
    return cases


def build_sandbox_payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": case["ticker"],
        "market": case["market"],
        "events": [
            {
                "event_id": f"bootstrap-{case['id']}",
                "event_type": "market_analysis_request",
                "content": case["input_narrative"],
                "source": "bootstrap_replay",
                "timestamp": case["run_timestamp"],
                "symbol": case["ticker"],
            }
        ],
        "narrative_guide": case["input_narrative"],
    }


def extract_agent_snapshots(result: dict[str, Any]) -> list[dict[str, Any]]:
    report = result.get("report") or {}
    perspective_detail = report.get("perspective_detail") or {}
    action_detail = report.get("action_detail") or {}

    snapshots: list[dict[str, Any]] = []
    for agent_id, perspective in perspective_detail.items():
        action = action_detail.get(agent_id) or {}
        market_bias = perspective.get("market_bias", "neutral")
        bias = market_bias if market_bias in {"bullish", "bearish", "neutral"} else "neutral"
        snapshots.append({
            "agent_id": agent_id,
            "bias": bias,
            "action_summary": action.get("rationale_summary", ""),
            "key_drivers": action.get("key_drivers", []),
            "observations": perspective.get("key_observations", []),
            "confidence": perspective.get("confidence", action.get("confidence", 0.0)),
            "action_horizon": action.get("horizon", ""),
        })
    return snapshots


def patch_case_snapshots(
    client: httpx.Client,
    case_id: str,
    agent_snapshots: list[dict[str, Any]],
    resolution_snapshot: dict[str, Any] | None,
) -> None:
    response = client.patch(
        f"{EVAL_SERVICE_URL}/api/cases/{case_id}/snapshots",
        json={
            "agent_snapshots": agent_snapshots,
            "resolution_snapshot": resolution_snapshot,
        },
    )
    response.raise_for_status()


def replay_cases(cases: Iterable[dict[str, Any]], dry_run: bool = False) -> None:
    backend_headers = {"X-API-Key": MAIN_BACKEND_API_KEY} if MAIN_BACKEND_API_KEY else {}

    with build_client() as client:
        for case in cases:
            if case.get("agent_count", 0) > 0:
                print(f"[skip] {case['run_id']} already has {case['agent_count']} agent snapshots")
                continue

            payload = build_sandbox_payload(case)
            print(f"[run] {case['run_id']} -> {case['ticker']} ({case['market']})")

            if dry_run:
                continue

            run_response = client.post(
                f"{MAIN_BACKEND_URL}/api/v1/sandbox/run",
                json=payload,
                headers=backend_headers,
            )
            run_response.raise_for_status()
            result = run_response.json()

            agent_snapshots = extract_agent_snapshots(result)
            resolution_snapshot = result.get("round_complete")

            patch_case_snapshots(
                client=client,
                case_id=case["id"],
                agent_snapshots=agent_snapshots,
                resolution_snapshot=resolution_snapshot,
            )
            print(f"[done] {case['run_id']} -> {len(agent_snapshots)} agent snapshots")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay bootstrap eval cases through the main sandbox backend.")
    parser.add_argument("--limit", type=int, default=25, help="Number of bootstrap cases to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Print planned runs without calling backend or patching")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with build_client() as client:
        cases = fetch_bootstrap_cases(client, limit=args.limit)
    replay_cases(cases, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

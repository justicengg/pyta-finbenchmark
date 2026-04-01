# PYTA Eval Service

Independent evaluation service for PYTA sandbox runs.

It receives completed sandbox outputs, stores eval cases, collects ground truth over time, and computes quality scores for internal benchmarking.

## Features

- webhook intake for completed sandbox runs
- manual bootstrap case creation for historical replay
- case detail and snapshot backfill APIs
- score summary and gradient endpoints for dashboard use
- local dashboard for inspection and debugging

## Tech Stack

- FastAPI
- SQLAlchemy
- APScheduler
- SQLite by default

## Project Structure

```text
app/
  api/         FastAPI routers
  db/          database session and models
  jobs/        scheduled jobs
  models/      eval_case / ground_truth / score
  services/    scoring and data-source services
dashboard/     local dashboard frontend
scripts/       bootstrap and replay utilities
tests/         minimal API tests
```

## Quick Start

```bash
cp .env.example .env
```

Fill the required env values, then start the service:

```bash
uvicorn app.main:app --reload --port 8001
```

Useful local URLs:

- Health: `http://127.0.0.1:8001/health`
- Dashboard: `http://127.0.0.1:8001/dashboard`
- OpenAPI: `http://127.0.0.1:8001/openapi.json`

## Environment Variables

Common variables:

- `DATABASE_URL`
- `ANTHROPIC_API_KEY`
- `JUDGE_MODEL`
- `MAIN_BACKEND_WEBHOOK_SECRET`
- `TUSHARE_TOKEN`

See `.env.example` for the current baseline.

## Core API Endpoints

| Method | Path | Purpose |
|------|------|------|
| `POST` | `/api/webhook/sandbox-run-completed` | ingest completed sandbox run |
| `POST` | `/api/cases/bootstrap` | create historical bootstrap case |
| `GET` | `/api/cases/` | list cases |
| `GET` | `/api/cases/{case_id}` | get case detail |
| `PATCH` | `/api/cases/{case_id}/snapshots` | backfill bootstrap snapshots |
| `GET` | `/api/scores/summary` | overall score summary |
| `GET` | `/api/scores/gradient-curve` | T+n gradient scoring view |

## Common Development Commands

Start the service:

```bash
uvicorn app.main:app --reload --port 8001
```

Run bootstrap replay smoke test:

```bash
NO_PROXY=127.0.0.1,localhost EVAL_SERVICE_URL=http://127.0.0.1:8001 MAIN_BACKEND_URL=http://127.0.0.1:8010 .venv/bin/python scripts/replay_bootstrap_cases.py --limit 5
```

Run bootstrap replay batch:

```bash
NO_PROXY=127.0.0.1,localhost EVAL_SERVICE_URL=http://127.0.0.1:8001 MAIN_BACKEND_URL=http://127.0.0.1:8010 .venv/bin/python scripts/replay_bootstrap_cases.py --limit 25
```

Run ground-truth collection manually:

```bash
python -c "from app.jobs.collect_gt import run; run()"
```

Run scoring manually:

```bash
python -c "from app.jobs.run_scoring import run; run()"
```

Run tests:

```bash
.venv/bin/python -m py_compile app/api/routers/cases.py scripts/replay_bootstrap_cases.py tests/test_cases_api.py
.venv/bin/python -c "from tests.test_cases_api import test_case_detail_and_snapshot_patch; test_case_detail_and_snapshot_patch(); print('test_cases_api ok')"
```

## Notes

- This service is intentionally separated from the main backend.
- The dashboard is an inspection surface, not the source of truth.
- Design and implementation notes live under `doc/claude/task/`.

from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import cases, pm_cases, pm_issues, scores, settings, webhook
from app.db import Base, engine
from app.jobs import collect_gt, pm_detect, run_scoring

DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic for production migrations)
    Base.metadata.create_all(bind=engine)

    # Scheduled jobs
    scheduler = BackgroundScheduler()
    # Collect ground truth daily at 09:00
    scheduler.add_job(collect_gt.run, "cron", hour=9, minute=0, id="collect_gt")
    # Run scoring daily at 09:30 (after GT collection)
    scheduler.add_job(run_scoring.run, "cron", hour=9, minute=30, id="run_scoring")
    # PM catch-up detection daily at 10:00
    scheduler.add_job(pm_detect.run, "cron", hour=10, minute=0, id="pm_detect")
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(
    title="PYTA Eval Service",
    version="0.1.0",
    description="Sandbox output quality evaluation — independent service",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(scores.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(pm_cases.router, prefix="/api/pm")
app.include_router(pm_issues.router, prefix="/api/pm")


@app.get("/health")
def health():
    return {"status": "ok", "service": "pyta-eval"}


@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard/", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD_DIR / "index.html")


if DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard/assets",
        StaticFiles(directory=DASHBOARD_DIR),
        name="dashboard-assets",
    )

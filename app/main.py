from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import cases, scores, webhook
from app.db import Base, engine
from app.jobs import collect_gt, run_scoring


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "pyta-eval"}

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import settings as settings_router
from app.db import Base, get_db


def build_test_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(settings_router.router, prefix="/api")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_judge_settings_configured_without_returning_key():
    client = build_test_client()

    initial = client.get("/api/settings/judge")
    assert initial.status_code == 200
    assert initial.json()["configured"] is False

    update = client.put(
        "/api/settings/judge",
        json={
            "api_key": "test-anthropic-key",
            "judge_model": "claude-sonnet-test",
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["configured"] is True
    assert body["judge_model"] == "claude-sonnet-test"
    assert "api_key" not in body

    detail = client.get("/api/settings/judge")
    assert detail.status_code == 200
    body = detail.json()
    assert body["configured"] is True
    assert body["judge_model"] == "claude-sonnet-test"
    assert "api_key" not in body

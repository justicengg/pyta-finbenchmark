from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import settings as settings_router
from app.db import Base, get_db
from app.models import AppSetting


def build_test_client() -> tuple[TestClient, sessionmaker]:
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
    return TestClient(app), TestingSessionLocal


def test_judge_settings_configured_without_returning_key():
    client, _ = build_test_client()

    initial = client.get("/api/settings/judge")
    assert initial.status_code == 200
    assert initial.json()["configured"] is False
    assert initial.json()["provider"] == "anthropic"
    assert initial.json()["enabled"] is False
    assert initial.json()["api_format"] == "anthropic"

    update = client.put(
        "/api/settings/judge",
        json={
            "provider": "openrouter",
            "api_key": "test-anthropic-key",
            "model": "openrouter/anthropic/claude-sonnet-test",
            "base_url": "https://openrouter.ai/api/v1",
            "api_format": "openai_compatible",
            "enabled": True,
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["configured"] is True
    assert body["provider"] == "openrouter"
    assert body["enabled"] is True
    assert body["model"] == "openrouter/anthropic/claude-sonnet-test"
    assert body["base_url"] == "https://openrouter.ai/api/v1"
    assert body["api_format"] == "openai_compatible"
    assert "api_key" not in body

    detail = client.get("/api/settings/judge")
    assert detail.status_code == 200
    body = detail.json()
    assert body["configured"] is True
    assert body["provider"] == "openrouter"
    assert body["enabled"] is True
    assert body["model"] == "openrouter/anthropic/claude-sonnet-test"
    assert body["base_url"] == "https://openrouter.ai/api/v1"
    assert body["api_format"] == "openai_compatible"
    assert "api_key" not in body


def test_legacy_anthropic_settings_are_still_supported():
    client, _ = build_test_client()

    update = client.put(
        "/api/settings/judge",
        json={
            "api_key": "legacy-anthropic-key",
            "judge_model": "claude-sonnet-legacy",
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-sonnet-legacy"
    assert body["judge_model"] == "claude-sonnet-legacy"
    assert body["configured"] is True
    assert "api_key" not in body

    detail = client.get("/api/settings/judge")
    assert detail.status_code == 200
    body = detail.json()
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-sonnet-legacy"
    assert body["judge_model"] == "claude-sonnet-legacy"
    assert body["configured"] is True
    assert "api_key" not in body


def test_legacy_database_key_is_still_supported():
    client, SessionLocal = build_test_client()

    db = SessionLocal()
    try:
        db.add(
            AppSetting(
                setting_key="judge.anthropic_api_key", setting_value="legacy-db-key"
            )
        )
        db.add(AppSetting(setting_key="judge.model", setting_value="claude-sonnet-db"))
        db.commit()
    finally:
        db.close()

    detail = client.get("/api/settings/judge")
    assert detail.status_code == 200
    body = detail.json()
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-sonnet-db"
    assert body["judge_model"] == "claude-sonnet-db"
    assert body["configured"] is True
    assert body["configured_via_settings"] is True
    assert "api_key" not in body


def test_provider_specific_settings_for_moonshot_are_accepted():
    client, _ = build_test_client()

    update = client.put(
        "/api/settings/judge",
        json={
            "provider": "moonshot",
            "api_key": "moonshot-key",
            "model": "moonshot-v1-8k",
            "base_url": "https://api.moonshot.cn/v1",
            "api_format": "openai_compatible",
            "enabled": True,
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["provider"] == "moonshot"
    assert body["model"] == "moonshot-v1-8k"
    assert body["base_url"] == "https://api.moonshot.cn/v1"
    assert body["api_format"] == "openai_compatible"
    assert body["configured"] is True
    assert "api_key" not in body

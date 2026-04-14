from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AppSetting
from app.services import llm_judge
from app.services.judge_client_factory import (
    AnthropicJudgeClient,
    OpenAICompatibleJudgeClient,
    create_judge_client,
)
from app.services.judge_runtime import load_judge_runtime_config


def _build_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_judge_runtime_config_reads_db_provider_settings(monkeypatch):
    session = _build_session()
    session.add(AppSetting(setting_key="judge.provider", setting_value="openrouter"))
    session.add(AppSetting(setting_key="judge.api_key", setting_value="db-key"))
    session.add(AppSetting(setting_key="judge.model", setting_value="db-model"))
    session.add(
        AppSetting(setting_key="judge.base_url", setting_value="https://example.com/v1")
    )
    session.add(
        AppSetting(setting_key="judge.api_format", setting_value="openai_compatible")
    )
    session.commit()

    monkeypatch.setenv("JUDGE_PROVIDER", "anthropic")
    monkeypatch.setenv("JUDGE_API_KEY", "env-key")
    monkeypatch.setenv("JUDGE_MODEL", "env-model")

    config = load_judge_runtime_config(session)

    assert config.provider == "openrouter"
    assert config.api_key == "db-key"
    assert config.model == "db-model"
    assert config.base_url == "https://example.com/v1"
    assert config.api_format == "openai_compatible"
    assert config.configured is True
    assert config.configured_via_settings is True


def test_create_judge_client_prefers_anthropic_native(monkeypatch):
    captured: dict[str, object] = {}

    class FakeMessageBlock:
        def __init__(self, text: str):
            self.text = text

    class FakeMessages:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                content=[FakeMessageBlock('{"total": 88, "rationale": "ok"}')]
            )

    class FakeAnthropic:
        def __init__(self, **kwargs):
            captured["init_kwargs"] = kwargs
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)

    client = create_judge_client(
        SimpleNamespace(
            provider="anthropic",
            api_key="anthropic-key",
            model="claude-opus-4-6",
            base_url="",
            api_format="anthropic",
        )
    )

    assert isinstance(client, AnthropicJudgeClient)

    result = client.complete(
        system_prompt="system",
        user_prompt="prompt",
        model="claude-opus-4-6",
    )

    assert captured["init_kwargs"] == {"api_key": "anthropic-key"}
    assert captured["kwargs"]["model"] == "claude-opus-4-6"
    assert result.text == '{"total": 88, "rationale": "ok"}'


def test_create_judge_client_prefers_openrouter_openai_compatible(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "openrouter-model",
                "choices": [
                    {
                        "message": {
                            "content": '{"total": 92, "rationale": "openrouter ok"}'
                        }
                    }
                ],
            }

    class FakeHttpxClient:
        def __init__(self, *, base_url: str, timeout: float):
            captured["init_kwargs"] = {"base_url": base_url, "timeout": timeout}

        def post(self, path: str, headers: dict, json: dict):
            captured["post"] = {"path": path, "headers": headers, "json": json}
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeHttpxClient)

    client = create_judge_client(
        SimpleNamespace(
            provider="openrouter",
            api_key="router-key",
            model="router-model",
            base_url="",
            api_format="openai_compatible",
        )
    )

    assert isinstance(client, OpenAICompatibleJudgeClient)

    result = client.complete(
        system_prompt="system",
        user_prompt="prompt",
        model="router-model",
    )

    assert captured["init_kwargs"]["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["post"]["path"] == "/chat/completions"
    assert captured["post"]["headers"]["Authorization"] == "Bearer router-key"
    assert result.text == '{"total": 92, "rationale": "openrouter ok"}'
    assert result.model == "openrouter-model"


def test_score_reasoning_uses_provider_aware_client(monkeypatch):
    class FakeClient:
        def complete(self, **kwargs):
            assert kwargs["model"] == "router-model"
            return SimpleNamespace(
                text='{"logical_coherence": 20, "evidence_grounding": 21, "specificity": 22, "consistency": 23, "total": 86, "rationale": "good"}',
                model="router-model",
            )

    monkeypatch.setattr(
        llm_judge,
        "load_judge_runtime_config",
        lambda: SimpleNamespace(
            provider="openrouter",
            api_key="router-key",
            model="router-model",
            base_url="https://openrouter.ai/api/v1",
            api_format="openai_compatible",
            configured=True,
            configured_via_settings=False,
        ),
    )
    monkeypatch.setattr(llm_judge, "create_judge_client", lambda config: FakeClient())

    result = llm_judge.score_reasoning(
        ticker="600036.SH",
        market="CN",
        input_narrative="test input",
        agent_snapshot={
            "agent_id": "agent-a",
            "bias": "bullish",
            "action_summary": "summary",
            "key_drivers": ["driver-a"],
            "observations": ["obs-a"],
        },
    )

    assert result["score"] == 0.86
    assert result["model"] == "router-model"
    assert result["total"] == 86

from __future__ import annotations

from dataclasses import dataclass

from app.services.runtime_settings import (
    get_judge_runtime_config,
    get_judge_runtime_config_without_session,
)

DEFAULT_PROVIDER = "anthropic"
DEFAULT_API_FORMAT = "anthropic"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class JudgeRuntimeConfig:
    provider: str
    api_key: str
    model: str
    base_url: str
    api_format: str
    configured: bool
    configured_via_settings: bool
    enabled: bool


def _normalize_config(raw: dict[str, str | bool]) -> JudgeRuntimeConfig:
    provider = str(raw.get("provider") or DEFAULT_PROVIDER).strip().lower()
    api_format = str(raw.get("api_format") or "").strip().lower().replace("-", "_")
    if not api_format:
        api_format = DEFAULT_API_FORMAT if provider == "anthropic" else "openai_compatible"

    return JudgeRuntimeConfig(
        provider=provider or DEFAULT_PROVIDER,
        api_key=str(raw.get("api_key") or ""),
        model=str(raw.get("model") or raw.get("judge_model") or ""),
        base_url=str(raw.get("base_url") or ""),
        api_format=api_format,
        configured=bool(raw.get("configured")),
        configured_via_settings=bool(raw.get("configured_via_settings")),
        enabled=bool(raw.get("enabled")),
    )


def load_judge_runtime_config(session=None) -> JudgeRuntimeConfig:
    raw = (
        get_judge_runtime_config(session)
        if session is not None
        else get_judge_runtime_config_without_session()
    )
    return _normalize_config(raw)

from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

JudgeProvider = Literal[
    "anthropic", "openai", "openrouter", "minimax", "moonshot", "zai", "custom"
]
JudgeApiFormat = Literal["anthropic", "openai_compatible", "custom"]

JUDGE_PROVIDER_KEY = "judge.provider"
JUDGE_API_KEY_KEY = "judge.api_key"
JUDGE_MODEL_KEY = "judge.model"
JUDGE_BASE_URL_KEY = "judge.base_url"
JUDGE_API_FORMAT_KEY = "judge.api_format"
JUDGE_ENABLED_KEY = "judge.enabled"
LEGACY_JUDGE_API_KEY_KEY = "judge.anthropic_api_key"


def get_setting(session: Session, key: str) -> str | None:
    row = session.query(AppSetting).filter(AppSetting.setting_key == key).one_or_none()
    return row.setting_value if row else None


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.query(AppSetting).filter(AppSetting.setting_key == key).one_or_none()
    if row is None:
        row = AppSetting(setting_key=key, setting_value=value)
        session.add(row)
    else:
        row.setting_value = value
    session.commit()


def _default_api_format(provider: str) -> str:
    if provider == "anthropic":
        return "anthropic"
    return "openai_compatible"


def get_judge_runtime_config(session: Session) -> dict[str, str | bool]:
    stored_provider = get_setting(session, JUDGE_PROVIDER_KEY)
    stored_key = get_setting(session, JUDGE_API_KEY_KEY)
    legacy_key = get_setting(session, LEGACY_JUDGE_API_KEY_KEY)
    stored_model = get_setting(session, JUDGE_MODEL_KEY)
    stored_base_url = get_setting(session, JUDGE_BASE_URL_KEY)
    stored_api_format = get_setting(session, JUDGE_API_FORMAT_KEY)
    stored_enabled = get_setting(session, JUDGE_ENABLED_KEY)

    effective_provider = stored_provider or "anthropic"
    effective_key = stored_key or legacy_key or settings.anthropic_api_key or ""
    effective_model = stored_model or settings.judge_model
    effective_base_url = stored_base_url or ""
    effective_api_format = stored_api_format or _default_api_format(effective_provider)
    parsed_enabled = _parse_bool(stored_enabled)
    effective_enabled = (
        parsed_enabled if parsed_enabled is not None else bool(effective_key)
    )
    configured_via_settings = any(
        value not in (None, "")
        for value in (
            stored_provider,
            stored_key,
            stored_model,
            stored_base_url,
            stored_api_format,
            stored_enabled,
        )
    ) or bool(legacy_key)
    return {
        "provider": effective_provider,
        "api_key": effective_key,
        "model": effective_model,
        "judge_model": effective_model,
        "base_url": effective_base_url,
        "api_format": effective_api_format,
        "enabled": effective_enabled,
        "configured": bool(effective_enabled and effective_key),
        "configured_via_settings": configured_via_settings,
    }


def get_judge_runtime_config_without_session() -> dict[str, str | bool]:
    db = SessionLocal()
    try:
        return get_judge_runtime_config(db)
    finally:
        db.close()

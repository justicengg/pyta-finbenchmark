from __future__ import annotations

from dataclasses import dataclass
import os

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

JUDGE_PROVIDER_KEY = "judge.provider"
JUDGE_API_KEY_KEY = "judge.api_key"
JUDGE_MODEL_KEY = "judge.model"
JUDGE_BASE_URL_KEY = "judge.base_url"
JUDGE_API_FORMAT_KEY = "judge.api_format"
LEGACY_JUDGE_API_KEY_KEY = "judge.anthropic_api_key"

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


def _get_setting(session: Session, key: str) -> str | None:
    row = session.query(AppSetting).filter(AppSetting.setting_key == key).one_or_none()
    if not row:
        return None
    value = (row.setting_value or "").strip()
    return value or None


def _first_setting(session: Session, *keys: str) -> str | None:
    for key in keys:
        value = _get_setting(session, key)
        if value:
            return value
    return None


def _normalize_provider(provider: str) -> str:
    value = provider.strip().lower()
    return value or DEFAULT_PROVIDER


def _normalize_api_format(provider: str, api_format: str) -> str:
    value = api_format.strip().lower().replace("-", "_")
    if value:
        return value
    if provider == "anthropic":
        return "anthropic"
    return "openai_compatible"


def _default_base_url(provider: str, api_format: str) -> str:
    if api_format == "anthropic":
        return ""
    if provider == "openrouter":
        return DEFAULT_OPENROUTER_BASE_URL
    if provider == "openai":
        return DEFAULT_OPENAI_BASE_URL
    return ""


def load_judge_runtime_config(session: Session | None = None) -> JudgeRuntimeConfig:
    owns_session = session is None
    db = session if session is not None else SessionLocal()
    try:
        db_provider = _first_setting(db, JUDGE_PROVIDER_KEY)
        db_api_key = _first_setting(db, JUDGE_API_KEY_KEY, LEGACY_JUDGE_API_KEY_KEY)
        db_model = _first_setting(db, JUDGE_MODEL_KEY)
        db_base_url = _first_setting(db, JUDGE_BASE_URL_KEY)
        db_api_format = _first_setting(db, JUDGE_API_FORMAT_KEY)

        env_provider = os.getenv("JUDGE_PROVIDER", "").strip()
        env_api_key = os.getenv("JUDGE_API_KEY", "").strip() or settings.anthropic_api_key.strip()
        env_model = os.getenv("JUDGE_MODEL", "").strip() or settings.judge_model.strip()
        env_base_url = os.getenv("JUDGE_BASE_URL", "").strip()
        env_api_format = os.getenv("JUDGE_API_FORMAT", "").strip()

        provider = _normalize_provider(db_provider or env_provider or DEFAULT_PROVIDER)
        api_format = _normalize_api_format(provider, db_api_format or env_api_format)
        api_key = db_api_key or env_api_key
        model = db_model or env_model
        base_url = db_base_url or env_base_url or _default_base_url(provider, api_format)

        return JudgeRuntimeConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            api_format=api_format,
            configured=bool(api_key),
            configured_via_settings=any((db_provider, db_api_key, db_model, db_base_url, db_api_format)),
        )
    finally:
        if owns_session:
            db.close()

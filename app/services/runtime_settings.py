from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

JUDGE_API_KEY_KEY = "judge.anthropic_api_key"
JUDGE_MODEL_KEY = "judge.model"


def get_setting(session: Session, key: str) -> str | None:
    row = session.query(AppSetting).filter(AppSetting.setting_key == key).one_or_none()
    return row.setting_value if row else None


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.query(AppSetting).filter(AppSetting.setting_key == key).one_or_none()
    if row is None:
        row = AppSetting(setting_key=key, setting_value=value)
        session.add(row)
    else:
        row.setting_value = value
    session.commit()


def get_judge_runtime_config(session: Session) -> dict[str, str | bool]:
    stored_key = get_setting(session, JUDGE_API_KEY_KEY)
    stored_model = get_setting(session, JUDGE_MODEL_KEY)
    effective_key = stored_key or settings.anthropic_api_key or ""
    effective_model = stored_model or settings.judge_model
    return {
        "api_key": effective_key,
        "judge_model": effective_model,
        "configured": bool(effective_key),
        "configured_via_settings": bool(stored_key),
    }


def get_judge_runtime_config_without_session() -> dict[str, str | bool]:
    db = SessionLocal()
    try:
        return get_judge_runtime_config(db)
    finally:
        db.close()

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.runtime_settings import (
    JUDGE_API_FORMAT_KEY,
    JUDGE_API_KEY_KEY,
    JUDGE_BASE_URL_KEY,
    JUDGE_ENABLED_KEY,
    JUDGE_PROVIDER_KEY,
    JUDGE_MODEL_KEY,
    get_judge_runtime_config,
    set_setting,
)

router = APIRouter(prefix="/settings", tags=["settings"])

JudgeProvider = Literal[
    "anthropic", "openai", "openrouter", "minimax", "moonshot", "zai", "custom"
]
JudgeApiFormat = Literal["anthropic", "openai_compatible", "custom"]


class JudgeSettingsUpdateRequest(BaseModel):
    provider: JudgeProvider | None = Field(default=None)
    api_key: str | None = Field(default=None)
    model: str | None = Field(default=None)
    judge_model: str | None = Field(default=None)
    base_url: str | None = Field(default=None)
    api_format: JudgeApiFormat | None = Field(default=None)
    enabled: bool | None = Field(default=None)


def _judge_settings_response(config: dict[str, str | bool]) -> dict[str, str | bool]:
    return {
        "provider": config["provider"],
        "configured": config["configured"],
        "configured_via_settings": config["configured_via_settings"],
        "enabled": config["enabled"],
        "model": config["model"],
        "judge_model": config["judge_model"],
        "base_url": config["base_url"],
        "api_format": config["api_format"],
    }


@router.get("/judge")
def get_judge_settings(db: Session = Depends(get_db)):
    config = get_judge_runtime_config(db)
    return _judge_settings_response(config)


@router.put("/judge")
def update_judge_settings(
    body: JudgeSettingsUpdateRequest, db: Session = Depends(get_db)
):
    current = get_judge_runtime_config(db)
    provider = body.provider or str(current["provider"])
    model = body.model if body.model is not None else body.judge_model

    if provider is not None:
        set_setting(db, JUDGE_PROVIDER_KEY, provider.strip())
    if body.api_key is not None:
        set_setting(db, JUDGE_API_KEY_KEY, body.api_key.strip())
    if model is not None:
        set_setting(db, JUDGE_MODEL_KEY, model.strip())
    if body.base_url is not None:
        set_setting(db, JUDGE_BASE_URL_KEY, body.base_url.strip())
    if body.api_format is not None:
        set_setting(db, JUDGE_API_FORMAT_KEY, body.api_format.strip())
    if body.enabled is not None:
        set_setting(db, JUDGE_ENABLED_KEY, "true" if body.enabled else "false")

    config = get_judge_runtime_config(db)
    return {"status": "updated", **_judge_settings_response(config)}

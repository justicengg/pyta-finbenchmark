from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.runtime_settings import (
    JUDGE_API_KEY_KEY,
    JUDGE_MODEL_KEY,
    get_judge_runtime_config,
    set_setting,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class JudgeSettingsUpdateRequest(BaseModel):
    api_key: str | None = Field(default=None)
    judge_model: str | None = Field(default=None)


@router.get("/judge")
def get_judge_settings(db: Session = Depends(get_db)):
    config = get_judge_runtime_config(db)
    return {
        "provider": "anthropic",
        "configured": config["configured"],
        "configured_via_settings": config["configured_via_settings"],
        "judge_model": config["judge_model"],
    }


@router.put("/judge")
def update_judge_settings(body: JudgeSettingsUpdateRequest, db: Session = Depends(get_db)):
    if body.api_key is not None:
        set_setting(db, JUDGE_API_KEY_KEY, body.api_key.strip())
    if body.judge_model is not None:
        set_setting(db, JUDGE_MODEL_KEY, body.judge_model.strip())

    config = get_judge_runtime_config(db)
    return {
        "status": "updated",
        "provider": "anthropic",
        "configured": config["configured"],
        "configured_via_settings": config["configured_via_settings"],
        "judge_model": config["judge_model"],
    }

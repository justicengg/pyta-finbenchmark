from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import anthropic
import httpx

from app.services.judge_runtime import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENROUTER_BASE_URL,
    JudgeRuntimeConfig,
)


class JudgeClientUnavailable(RuntimeError):
    """Raised when the judge cannot be constructed for the configured provider."""


@dataclass(frozen=True)
class JudgeCompletion:
    text: str
    model: str


class JudgeClient(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 512,
    ) -> JudgeCompletion: ...


def _extract_anthropic_text(message: object) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "".join(parts).strip()


def _extract_openai_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    return str(content or "").strip()


class AnthropicJudgeClient:
    def __init__(self, api_key: str, base_url: str | None = None):
        kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**kwargs)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 512,
    ) -> JudgeCompletion:
        message = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return JudgeCompletion(text=_extract_anthropic_text(message), model=model)


class OpenAICompatibleJudgeClient:
    def __init__(self, api_key: str, base_url: str):
        if not base_url:
            raise JudgeClientUnavailable("OpenAI-compatible judge requires a base_url")
        self._api_key = api_key
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=60.0)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 512,
    ) -> JudgeCompletion:
        response = self._client.post(
            "/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return JudgeCompletion(
            text=_extract_openai_text(payload),
            model=str(payload.get("model") or model),
        )


def _default_openai_base_url(provider: str) -> str:
    if provider == "openrouter":
        return DEFAULT_OPENROUTER_BASE_URL
    if provider == "openai":
        return DEFAULT_OPENAI_BASE_URL
    return ""


def create_judge_client(config: JudgeRuntimeConfig) -> JudgeClient:
    if not config.api_key:
        raise JudgeClientUnavailable("Judge API key is not configured")

    provider = config.provider.strip().lower()
    api_format = config.api_format.strip().lower()
    if api_format == "anthropic" and provider == "anthropic":
        return AnthropicJudgeClient(api_key=config.api_key, base_url=config.base_url or None)

    base_url = config.base_url or _default_openai_base_url(provider)
    if not base_url:
        raise JudgeClientUnavailable(
            f"OpenAI-compatible judge provider '{provider}' requires a base_url"
        )
    return OpenAICompatibleJudgeClient(api_key=config.api_key, base_url=base_url)

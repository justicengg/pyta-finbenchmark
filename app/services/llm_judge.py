"""
LLM-as-Judge module for evaluating agent reasoning quality.
Uses claude-opus-4-6 with a structured rubric.
"""

from __future__ import annotations

import json
import logging

import anthropic

from app.config import settings
from app.services.runtime_settings import get_judge_runtime_config_without_session

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None
_client_api_key: str | None = None


class LLMJudgeUnavailable(RuntimeError):
    """Raised when the judge cannot run due to local configuration."""


def _get_client() -> anthropic.Anthropic:
    global _client, _client_api_key
    config = get_judge_runtime_config_without_session()
    api_key = str(config["api_key"] or "")
    if not api_key:
        raise LLMJudgeUnavailable("ANTHROPIC_API_KEY is not configured")
    if _client is None or _client_api_key != api_key:
        _client = anthropic.Anthropic(api_key=api_key)
        _client_api_key = api_key
    return _client


SYSTEM_PROMPT = """你是一位资深市场分析师，负责评估 AI 沙盘推演系统中各参与者 Agent 的推演质量。
你的评估必须严格、客观，不受结果好坏影响——好的推演过程即使方向判断错误也可能得高分，差的推演即使方向碰巧正确也应得低分。
只返回 JSON，不附加任何解释文字。"""

JUDGE_PROMPT_TEMPLATE = """请评估以下 Agent 的推演质量。

市场背景：{ticker}（{market}）
输入指令：{input_narrative}
Agent 角色：{agent_title}（{agent_subtitle}）

Agent 分析内容：
- 方向判断：{bias}
- 行动摘要：{action_summary}
- 关键驱动因素：{key_drivers}
- 市场观察：{observations}

请对以下 4 个维度各打 0–25 分：

1. **logical_coherence**（逻辑自洽性）：推理是否从前提逻辑地导出结论？中间有无跳跃或矛盾？
2. **evidence_grounding**（论据扎实性）：论据是否来自输入信息？还是泛泛而谈、套用通用判断？
3. **specificity**（具体性）：分析是否针对当前具体情境？还是可以套用到任何类似场景的套话？
4. **consistency**（内外一致性）：偏多/偏空的最终判断，与推理内容和关键驱动因素是否一致？

返回格式（JSON only）：
{{
  "logical_coherence": <0-25>,
  "evidence_grounding": <0-25>,
  "specificity": <0-25>,
  "consistency": <0-25>,
  "total": <0-100>,
  "rationale": "<2-3 句评语，说明主要失分或得分原因>"
}}"""


def score_reasoning(
    ticker: str,
    market: str,
    input_narrative: str,
    agent_snapshot: dict,
) -> dict:
    """
    Score a single agent's reasoning quality.

    Returns:
        {
            "logical_coherence": int,
            "evidence_grounding": int,
            "specificity": int,
            "consistency": int,
            "total": int,           # sum of above, 0–100
            "score": float,         # total / 100, normalized to 0.0–1.0
            "rationale": str,
            "model": str,
        }
    """
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        ticker=ticker,
        market=market,
        input_narrative=input_narrative[:800],  # guard against very long inputs
        agent_title=agent_snapshot.get("agent_id", "Unknown"),
        agent_subtitle=agent_snapshot.get("subtitle", ""),
        bias=agent_snapshot.get("bias", "unknown"),
        action_summary=agent_snapshot.get("action_summary", ""),
        key_drivers=", ".join(agent_snapshot.get("key_drivers", [])),
        observations="; ".join(agent_snapshot.get("observations", [])),
    )

    runtime_config = get_judge_runtime_config_without_session()
    client = _get_client()
    message = client.messages.create(
        model=str(runtime_config["judge_model"] or settings.judge_model),
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM judge returned non-JSON: %s", raw[:200])
        raise ValueError(f"LLM judge returned non-JSON output: {raw[:200]}")

    total = result.get("total") or sum(
        result.get(k, 0)
        for k in ("logical_coherence", "evidence_grounding", "specificity", "consistency")
    )
    result["total"] = total
    result["score"] = round(total / 100, 4)
    result["model"] = str(runtime_config["judge_model"] or settings.judge_model)
    return result

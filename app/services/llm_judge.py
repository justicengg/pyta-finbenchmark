"""
LLM-as-Judge module for evaluating agent reasoning quality.
Uses claude-opus-4-6 with a structured rubric.
"""

from __future__ import annotations

import json
import logging

from app.services.judge_client_factory import (
    JudgeClientUnavailable,
    create_judge_client,
)
from app.services.judge_runtime import JudgeRuntimeConfig, load_judge_runtime_config

logger = logging.getLogger(__name__)


class LLMJudgeUnavailable(RuntimeError):
    """Raised when the judge cannot run due to local configuration."""


def _get_client(config: JudgeRuntimeConfig):
    try:
        return create_judge_client(config)
    except JudgeClientUnavailable as exc:
        raise LLMJudgeUnavailable(str(exc)) from exc


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


# ── Primary-Market Rubric ──────────────────────────────────────────────────────

PM_SYSTEM_PROMPT = """你是一位资深一级市场投资分析师，负责评估 AI 一级市场推演系统的报告质量。
你的评估必须严格、客观，关注推理过程而非结论本身——好的分析框架即使最终判断有误也可能得高分。
只返回 JSON，不附加任何解释文字。"""

PM_JUDGE_PROMPT_TEMPLATE = """请评估以下一级市场投资推演报告的推理质量。

公司：{company_name}（{sector}）
投资决策：{decision}（confidence: {confidence}）

报告内容摘要：
- 关键假设：{key_assumptions}
- 维度分析：{dimension_scores}
- 风险分岔：{path_forks}
- 财务分析：{financial_analysis}
- 监测指标：{monitoring_triggers}

请对以下 4 个维度各打 0–25 分：

1. **assumption_quality**（假设质量）：关键假设是否抓住核心风险？hard/soft 分级是否合理？假设是否可证伪？
2. **dimension_coverage**（维度覆盖）：6 个维度是否有针对性分析？uncertainty score 论据是否充分？是否有维度被敷衍带过？
3. **financial_depth**（财务深度）：财务分析是否深入？估值逻辑是否清晰？benchmark 比较是否合理？数据引用是否具体？
4. **risk_identification**（风险识别）：风险识别是否全面？path_forks 场景推演是否有决策价值？正反面是否均衡？

返回格式（JSON only）：
{{
  "assumption_quality": <0-25>,
  "dimension_coverage": <0-25>,
  "financial_depth": <0-25>,
  "risk_identification": <0-25>,
  "total": <0-100>,
  "rationale": "<2-3 句评语，说明主要失分或得分原因>"
}}"""


def score_pm_reasoning(
    company_name: str,
    sector: str,
    decision: str,
    confidence: float,
    report_snapshot: dict,
) -> dict:
    """
    Score a primary-market report's reasoning quality.

    Returns:
        {
            "assumption_quality": int,
            "dimension_coverage": int,
            "financial_depth": int,
            "risk_identification": int,
            "total": int,           # sum of above, 0–100
            "score": float,         # total / 100, normalized to 0.0–1.0
            "rationale": str,
            "model": str,
        }
    """
    # Extract key sections from report_snapshot
    key_assumptions = report_snapshot.get("key_assumptions", [])
    dimension_scores = report_snapshot.get("dimension_scores", {})
    path_forks = report_snapshot.get("path_forks", [])
    financial_analysis = report_snapshot.get("financial_analysis", {})
    monitoring_triggers = report_snapshot.get("monitoring_triggers", [])

    prompt = PM_JUDGE_PROMPT_TEMPLATE.format(
        company_name=company_name,
        sector=sector or "未知",
        decision=decision,
        confidence=confidence,
        key_assumptions=json.dumps(key_assumptions, ensure_ascii=False)[:1200],
        dimension_scores=json.dumps(dimension_scores, ensure_ascii=False)[:800],
        path_forks=json.dumps(path_forks, ensure_ascii=False)[:800],
        financial_analysis=json.dumps(financial_analysis, ensure_ascii=False)[:800],
        monitoring_triggers=json.dumps(monitoring_triggers, ensure_ascii=False)[:400],
    )

    runtime_config = load_judge_runtime_config()
    client = _get_client(runtime_config)
    completion = client.complete(
        system_prompt=PM_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=str(runtime_config.model),
        max_tokens=512,
    )

    raw = completion.text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("PM LLM judge returned non-JSON: %s", raw[:200])
        raise ValueError(f"PM LLM judge returned non-JSON output: {raw[:200]}")

    total = result.get("total") or sum(
        result.get(k, 0)
        for k in (
            "assumption_quality",
            "dimension_coverage",
            "financial_depth",
            "risk_identification",
        )
    )
    result["total"] = total
    result["score"] = round(total / 100, 4)
    result["model"] = completion.model
    return result


# ── Secondary-Market Scoring ──────────────────────────────────────────────────


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

    runtime_config = load_judge_runtime_config()
    client = _get_client(runtime_config)
    completion = client.complete(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt,
        model=str(runtime_config.model),
        max_tokens=512,
    )

    raw = completion.text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM judge returned non-JSON: %s", raw[:200])
        raise ValueError(f"LLM judge returned non-JSON output: {raw[:200]}")

    total = result.get("total") or sum(
        result.get(k, 0)
        for k in (
            "logical_coherence",
            "evidence_grounding",
            "specificity",
            "consistency",
        )
    )
    result["total"] = total
    result["score"] = round(total / 100, 4)
    result["model"] = completion.model
    return result

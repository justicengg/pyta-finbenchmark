# 2026-04-02 LLM Judge 认证保护

## 目标

修复当前 `reasoning_quality` 评分阶段的无认证报错问题。

## 问题现状

当前已确认：

1. `ANTHROPIC_API_KEY` 未加载
2. scoring 进入 `reasoning_quality` 时会对每个 agent 都报一次错误
3. 这会污染日志，但并不影响 `direction_accuracy` 和 `resolution_accuracy`

## 本轮目标

1. 对无 key 场景做显式判断
2. 将其视为可解释的降级，而不是异常
3. 保持其他评分维度正常运行

## 验收标准

1. 无 key 时不再刷重复错误日志
2. scoring 仍能继续产出自动评分维度
3. `reasoning_quality` 缺失原因可被明确解释

## 实际结果

本轮已完成：

1. 在 `llm_judge` 中增加 `LLMJudgeUnavailable`
2. 当 `ANTHROPIC_API_KEY` 未配置时，显式返回“judge 不可用”
3. 在 `scorer` 中把该情况视为降级，而不是异常
4. 避免按 agent 连续刷错误日志

## 当前结论

1. `reasoning_quality` 当前仍不会出数
2. 原因已明确：本地未配置 `ANTHROPIC_API_KEY`
3. 这不再影响：
   - `direction_accuracy`
   - `resolution_accuracy`
   - dashboard summary / gradient

## 后续动作

如果要真正打通 `reasoning_quality`，下一步只需要：

1. 配置有效的 Anthropic API key
2. 重新执行 `run_scoring`

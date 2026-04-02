# 2026-04-02 GT 收集器加固

## 目标

修复当前 ground truth 收集卡住的问题，让 `collect_gt` 至少能在有限时间内完成一次遍历，而不是被单个价格源长时间阻塞。

## 问题现状

当前已确认：

1. bootstrap replay 已完成
2. `run_scoring` 之所以没有结果，不是评分逻辑问题
3. 真正阻塞点在 `price_collector.py`
4. 单条 `cross_verify(...)` 调用也会长时间阻塞

## 本轮目标

1. 给价格获取链增加可控超时
2. 保证单个数据源失败或卡住时能快速降级
3. 让 `collect_gt` 能继续处理后续 case，而不是被单个 ticker 卡死

## 任务拆分

1. 为 fetch 函数增加超时执行包装
2. 调整 `get_price_direction` / `cross_verify` 的降级逻辑
3. 增加最小测试或脚本级验证
4. 手动重跑 `collect_gt`
5. 检查 `ground_truth` 是否开始落库

## 验收标准

1. 单条 `cross_verify(...)` 不再无限等待
2. `collect_gt` 能在可接受时间内结束
3. 数据库中 `ground_truth` 数量开始增加

## 实际结果

本轮已完成：

1. 为价格抓取链增加超时保护
2. 修正 A 股 yfinance ticker 映射
3. 修正 yfinance 返回值解析中的 `Series -> float` 问题
4. 将 GT 收集默认顺序改为快源优先

当前已验证：

1. `ground_truth` 已从 `0` 增长到 `13`
2. `scores` 已从 `0` 增长到 `37`
3. dashboard summary 已出现真实数据：
   - `direction_accuracy.avg_score = 0.4857`
   - `resolution_accuracy.avg_score = 0.25`
4. gradient curve 已出现可用点位

## 仍然存在的问题

1. `reasoning_quality` 仍然为 `null`
2. 根因不是评分主流程，而是 LLM judge 当前缺少认证配置
3. `event_alignment` 当前也尚未产出有效评分

## 结论

这一轮已经把系统从“GT 完全卡住”推进到“部分评分可见、dashboard 开始出数”。

下一步若继续，应优先处理：

1. LLM judge 认证配置
2. `reasoning_quality` 评分恢复
3. GT 全量收集完成后的二次 scoring

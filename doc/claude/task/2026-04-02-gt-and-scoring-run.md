# 2026-04-02 GT 收集与 Scoring 执行

## 目标

在 bootstrap replay 已完成后，继续手动执行：

1. ground truth 收集
2. scoring

目标是让 eval dashboard 顶部的 summary / gradient / case score 开始出现真实数据。

## 执行步骤

1. 确认 eval-service 当前状态干净
2. 手动触发 `collect_gt`
3. 手动触发 `run_scoring`
4. 校验：
   - `/api/scores/summary`
   - `/api/scores/gradient-curve`
   - `/api/scores/case/{case_id}`

## 验收标准

1. score summary 返回不再全是 `null`
2. gradient curve 出现可用点位
3. 至少一个 bootstrap case detail 能查到 score

## 当前执行结果

1. 已确认 bootstrap 样本中不存在 `600036.SH`（招商银行）
2. 已手动触发 `collect_gt`
3. 已手动触发 `run_scoring`
4. 当前数据库状态仍为：
   - `ground_truth = 0`
   - `scores = 0`
   - `status = pending`

## 当前阻塞点

阻塞不在 scoring，而在 GT 取数。

已确认：

1. `collect_gt` 进程仍在运行
2. 单条 `cross_verify(...)` 调用也会长时间阻塞
3. 说明当前问题在价格数据源获取链，而不是 dashboard 或评分路由

## 结论

当前不能继续得到有效评分结果，原因是：

1. ground truth 尚未成功落库
2. 没有可评分的 complete case
3. `run_scoring` 当前只是空跑验证

后续若继续推进，应优先排查：

1. `price_collector.py` 的外部数据源超时与降级策略
2. AKShare / yfinance 在当前环境中的可用性
3. GT 收集是否需要先做单源、短超时版本

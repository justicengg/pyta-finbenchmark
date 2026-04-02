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
4. 当前数据库状态已推进为：
   - `ground_truth = 13`
   - `scores = 37`
   - `status` 已出现 `collecting / complete`

## 当前阻塞点

阻塞不在 scoring，而在 GT 取数。

已确认：

1. `collect_gt` 进程仍在运行
2. 单条 `cross_verify(...)` 调用也会长时间阻塞
3. 说明当前问题在价格数据源获取链，而不是 dashboard 或评分路由

## 结论

当前已经可以得到部分有效评分结果，但还没有全维度完整评分。

已确认：

1. `direction_accuracy` 已开始产出
2. `resolution_accuracy` 已开始产出
3. `reasoning_quality` 仍未产出

当前剩余阻塞点变为：

1. LLM judge 缺少认证配置
2. GT 尚未全量完成
3. `event_alignment` 仍未进入有效评分

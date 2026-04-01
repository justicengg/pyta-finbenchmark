# 2026-04-01 Bootstrap Replay 实施

## 目标

为 bootstrap 用例补齐 `agent_snapshots`，打通最小评测闭环：

1. 为 eval-service 增加 `PATCH /cases/{case_id}/snapshots`
2. 新建 `scripts/replay_bootstrap_cases.py`
3. 通过主后端 `POST /sandbox/run` 回放 bootstrap narrative
4. 从 sandbox 返回中提取 agent snapshots
5. 回写到对应 bootstrap EvalCase

## 任务边界

本轮不做：

- dashboard 优化
- reasoning quality 评分优化
- GT 全量收集调优
- webhook 幂等逻辑重构

## 验收目标

1. bootstrap case 可以通过 PATCH 回填 `agent_snapshots`
2. replay 脚本至少能对少量 case 成功跑通
3. `GET /api/cases?source=bootstrap` 中的 case `agent_count > 0`

## 状态

- 已完成接口与脚本实现
- 已完成本地代码级验证
- 已完成 5 条 bootstrap case 真实 replay smoke test
- 已启动 bootstrap 全量 replay，当前进度 `23 / 25`

## 实际落地

1. 新增 `PATCH /api/cases/{case_id}/snapshots`
2. `GET /api/cases/{case_id}` 现在返回详情字段：
   - `input_narrative`
   - `agent_snapshots`
   - `resolution_snapshot`
3. 新增 `scripts/replay_bootstrap_cases.py`
   - 拉取 bootstrap cases
   - 调用主后端 `/api/v1/sandbox/run`
   - 提取 agent snapshots
   - PATCH 回 eval-service
4. 新增最小 API 测试 `tests/test_cases_api.py`
5. 修正 replay 脚本主后端路径
   - 从 `/sandbox/run` 更正为 `/api/v1/sandbox/run`
6. 实际 smoke test 时补充本地代理绕过
   - 使用 `NO_PROXY=127.0.0.1,localhost`
   - 避免 localhost 请求被代理层错误拦截为 `403`

## 验证结果

- `.venv/bin/python -m py_compile app/api/routers/cases.py scripts/replay_bootstrap_cases.py tests/test_cases_api.py`
- `.venv/bin/python -c "from tests.test_cases_api import test_case_detail_and_snapshot_patch; test_case_detail_and_snapshot_patch(); print('test_cases_api ok')"`
- `curl -i http://127.0.0.1:8010/health`
- `curl -i http://127.0.0.1:8011/health`
- `curl -i "http://127.0.0.1:8011/api/cases/?source=bootstrap&limit=5&offset=0"`
- `NO_PROXY=127.0.0.1,localhost EVAL_SERVICE_URL=http://127.0.0.1:8011 MAIN_BACKEND_URL=http://127.0.0.1:8010 .venv/bin/python scripts/replay_bootstrap_cases.py --limit 5`

### 真实 smoke test 结果

- 前 5 条 bootstrap case 已全部回填成功
- 每条 case 当前均满足：
  - `agent_count = 5`
  - `has_resolution = true`
- 示例成功 case：
  - `f02078a2-41cb-413c-b321-45649ccf3567`
  - `run_id = bootstrap-688256.SH-2026-01-15`

### 全量 replay 进展

- 已启动 `--limit 25` 的全量 bootstrap replay
- 当前已回填 `23 / 25`
- 这说明：
  - replay 脚本可持续执行
  - `PATCH /snapshots` 回填链路正常
  - eval-service dashboard 已能消费大多数 bootstrap snapshots

## 未完成项

- 剩余 `2` 条 bootstrap case 回填完成确认
- 如有需要，再触发 GT 收集与后续评分链验证

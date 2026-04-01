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
- 待服务启动后执行真实 replay smoke test

## 实际落地

1. 新增 `PATCH /api/cases/{case_id}/snapshots`
2. `GET /api/cases/{case_id}` 现在返回详情字段：
   - `input_narrative`
   - `agent_snapshots`
   - `resolution_snapshot`
3. 新增 `scripts/replay_bootstrap_cases.py`
   - 拉取 bootstrap cases
   - 调用主后端 `/sandbox/run`
   - 提取 agent snapshots
   - PATCH 回 eval-service
4. 新增最小 API 测试 `tests/test_cases_api.py`

## 验证结果

- `.venv/bin/python -m py_compile app/api/routers/cases.py scripts/replay_bootstrap_cases.py tests/test_cases_api.py`
- `.venv/bin/python -c "from tests.test_cases_api import test_case_detail_and_snapshot_patch; test_case_detail_and_snapshot_patch(); print('test_cases_api ok')"`

## 未完成项

- 本机 `127.0.0.1:8000` 与 `127.0.0.1:8001` 当前未运行，因此这轮未执行真实 replay dry-run

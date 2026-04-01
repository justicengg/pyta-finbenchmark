# Bootstrap Replay Runbook

## 目的

用本地 `main backend + eval-service` 跑一轮约 5 条 bootstrap case 的 smoke test，确认：

- bootstrap case 可以被 replay
- `agent_snapshots` 可以成功回填
- `agent_count > 0`

## 步骤 1：启动主后端

```bash
cd /Users/sikaijiang/Desktop/pyta-research-worktrees/secondary-market-mvp
uv run uvicorn src.api.app:app --host 127.0.0.1 --port 8010
```

预期：

- 看到 `Uvicorn running on http://127.0.0.1:8010`

## 步骤 2：启动 eval-service

新开一个终端执行：

```bash
cd /Users/sikaijiang/Desktop/pyta-research-worktrees/secondary-market-mvp/eval-service
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
```

预期：

- 看到 `Uvicorn running on http://127.0.0.1:8011`

## 步骤 3：确认 bootstrap case 已存在

新开第三个终端执行：

```bash
cd /Users/sikaijiang/Desktop/pyta-research-worktrees/secondary-market-mvp/eval-service
curl http://127.0.0.1:8011/api/cases/?source=bootstrap&limit=5&offset=0
```

预期：

- 返回 JSON
- `items` 中有 bootstrap case

## 步骤 4：执行 5 条 bootstrap replay

```bash
cd /Users/sikaijiang/Desktop/pyta-research-worktrees/secondary-market-mvp/eval-service
EVAL_SERVICE_URL=http://127.0.0.1:8011 MAIN_BACKEND_URL=http://127.0.0.1:8010 .venv/bin/python scripts/replay_bootstrap_cases.py --limit 5
```

预期：

- 输出每条 case 的 replay 日志
- 没有 4xx / 5xx 报错
- 命令正常结束

## 步骤 5：检查 snapshots 是否回填成功

先看列表：

```bash
curl http://127.0.0.1:8011/api/cases/?source=bootstrap&limit=5&offset=0
```

再挑一个 `case_id` 看详情：

```bash
curl http://127.0.0.1:8011/api/cases/<CASE_ID>
```

重点确认：

- `agent_count > 0`
- `agent_snapshots` 非空
- `resolution_snapshot` 已写入

## 步骤 6：如果失败，优先检查

```bash
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8011/health
```

同时检查两个服务终端是否有报错。

## 回传给 Codex 的信息

执行完成后，回传：

1. replay 脚本终端输出
2. 一个成功 case 的详情 JSON
3. 如果失败，贴出报错和对应服务日志

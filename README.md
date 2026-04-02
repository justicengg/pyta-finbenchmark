# PYTA 推演质量评测服务

这是一个独立于主后端运行的评测服务。

它的职责不是参与推演，而是在 sandbox run 完成之后，负责保存评测用例、回收真实世界结果、计算评分，并为后续优化提供依据。

## 这套系统解决什么问题

它主要解决 3 件事：

1. 把一次推演结果沉淀成可评测的 case
2. 在 T+N 时间点回收真实结果，验证推演质量
3. 把评测结果反哺给 prompt、agent、博弈解析和后续编排

一句话理解：

`主后端负责推演，eval-service 负责验证推演。`

## 当前核心功能

目前已经具备的能力包括：

1. 接收主后端 webhook 推送的 completed sandbox run
2. 手动创建 bootstrap 历史用例
3. 通过 replay 回填 bootstrap case 的 `agent_snapshots`
4. 提供 case 列表、case 详情和评分查询接口
5. 提供内部 dashboard 作为查看面

## 主要模块

项目结构可以简单理解为：

```text
app/
  api/         接口层
  db/          数据库连接与表模型
  jobs/        定时任务
  models/      eval_case / ground_truth / score
  services/    评分与数据服务
dashboard/     内部查看页面
scripts/       bootstrap / replay 脚本
tests/         最小验证测试
```

## 如何启动

先准备环境变量：

```bash
cp .env.example .env
```

然后启动服务：

```bash
uvicorn app.main:app --reload --port 8001
```

## 常用开发动作

### 1. replay bootstrap 用例

少量 smoke test：

```bash
NO_PROXY=127.0.0.1,localhost EVAL_SERVICE_URL=http://127.0.0.1:8001 MAIN_BACKEND_URL=http://127.0.0.1:8010 .venv/bin/python scripts/replay_bootstrap_cases.py --limit 5
```

全量回填：

```bash
NO_PROXY=127.0.0.1,localhost EVAL_SERVICE_URL=http://127.0.0.1:8001 MAIN_BACKEND_URL=http://127.0.0.1:8010 .venv/bin/python scripts/replay_bootstrap_cases.py --limit 25
```

### 2. 手动触发 GT 收集

```bash
python -c "from app.jobs.collect_gt import run; run()"
```

### 3. 手动触发评分

```bash
python -c "from app.jobs.run_scoring import run; run()"
```

## 接手时要注意

1. 这是独立仓库，不是主后端普通子目录
2. 优先检查 case intake、snapshot 回填、GT 回收，再看 dashboard
3. README 只保留入口信息，设计推导放在 `doc/claude/task/` 和 Obsidian 笔记
4. dashboard 是查看面，不是 source of truth

## 相关文档

如果要继续接手，建议优先看：

1. `doc/claude/task/2026-04-01-bootstrap-replay-implementation.md`
2. `doc/claude/task/2026-04-02-bootstrap-replay-runbook.md`
3. `doc/claude/task/` 下最近的任务文档

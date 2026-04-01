# pyta-eval

PYTA 推演质量评测服务。独立于主后端运行。

## 启动

```bash
cp .env.example .env
# 填写 .env 中的配置

poetry install
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

主后端运行在 8000，eval service 运行在 8001。

## 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/webhook/sandbox-run-completed | 接收主后端推送 |
| POST | /api/cases/bootstrap | 手动创建历史用例 |
| GET | /api/cases/ | 查询用例列表 |
| GET | /api/scores/gradient-curve | 梯度准确率曲线 |
| GET | /api/scores/summary | 各维度汇总分数 |
| GET | /health | 健康检查 |

## 手动触发任务

```bash
# 立即执行 ground truth 收集（不等定时任务）
python -c "from app.jobs.collect_gt import run; run()"

# 立即执行评分
python -c "from app.jobs.run_scoring import run; run()"
```

## 设计文档

见主仓库：`doc/claude/task/2026-04-01-CC-eval-system-design.md`

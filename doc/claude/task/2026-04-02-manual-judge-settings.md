# 2026-04-02 手动配置 Judge API Key

## 目标

给 eval-service 增加一个本地设置入口，让使用者可以自己在系统中填写 Judge API key，而不是要求把 key 直接贴给开发 agent。

## 设计边界

本轮只处理 judge 配置，不扩展成完整通用设置系统。

需要满足：

1. 服务端可持久化保存 key
2. 前端 dashboard 有设置入口
3. 前端不回显完整 key
4. `llm_judge` 可优先读取手动配置

## 任务拆分

1. 新增设置模型与服务
2. 新增 judge settings API
3. 修改 `llm_judge` 读取逻辑
4. 在 dashboard 增加设置入口与保存表单
5. 验证：
   - 可保存
   - `configured` 状态可见
   - 不返回明文 key

## 验收标准

1. 用户可通过 dashboard 手动填写 judge key
2. API 返回 `configured: true/false`
3. `reasoning_quality` 不再依赖手改 `.env`

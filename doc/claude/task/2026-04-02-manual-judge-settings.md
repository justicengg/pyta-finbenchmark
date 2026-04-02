# 2026-04-02 手动配置 Judge Provider

## 目标

给 eval-service 增加一个本地设置入口，让使用者可以自己在系统中填写 Judge provider 配置，而不是要求把 key 直接贴给开发 agent。

## 设计边界

本轮只处理 judge 配置，不扩展成完整通用设置系统。

需要满足：

1. 服务端可持久化保存 provider / key / model / base_url / api_format / enabled
2. 前端 dashboard 有设置入口
3. 前端不回显完整 key
4. `llm_judge` 可优先读取手动配置
5. 兼容旧版 Anthropic-only 的 `judge_model` 入参

## 任务拆分

1. 新增 provider-aware 设置模型与服务
2. 新增/扩展 judge settings API
3. 修改 `llm_judge` 读取逻辑与 provider client factory
4. 在 dashboard 增加 Provider / Model / Base URL / API Format / Enabled 表单
5. 验证：
   - 可保存
   - `configured` 状态可见
   - 不返回明文 key
   - Anthropic / OpenRouter 都有明确配置入口

## 验收标准

1. 用户可通过 dashboard 手动填写 judge provider 配置
2. API 返回 `configured: true/false`
3. `reasoning_quality` 不再依赖手改 `.env`
4. 旧版 Anthropic-only 请求仍可继续工作
5. OpenRouter 这类第三方兼容网关可通过 `base_url + api_format` 接入

## 当前 provider 列表

1. `anthropic`
2. `openai`
3. `openrouter`
4. `minimax`
5. `moonshot`
6. `zai`
7. `custom`

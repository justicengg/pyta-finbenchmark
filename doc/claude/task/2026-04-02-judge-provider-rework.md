# 2026-04-02 Judge Provider 重构

## 目标

把 reasoning judge 从 Anthropic 单 provider 直连，升级成 provider-aware 调用层，至少支持：

1. `anthropic` 原生
2. `openrouter`
3. `base_url`
4. `api_format`

## 设计边界

本轮只改 judge client / provider 调用层，不改 dashboard，也不改 settings API 的 UI 交互。

需要满足：

1. `llm_judge` 不再写死 Anthropic SDK
2. 支持基于 provider 的 client factory
3. 缺配置时继续优雅降级
4. 现有 `scorer` 调用入口保持稳定

## 任务拆分

1. 增加 provider-aware judge config 读取
2. 抽象 judge client factory
3. 改造 `llm_judge` 调用入口
4. 补充最小测试

## 验收标准

1. `anthropic` 配置可继续工作
2. `openrouter` 可作为 judge provider 接入
3. 未配置时仍然能安全降级，不影响 scoring 主流程

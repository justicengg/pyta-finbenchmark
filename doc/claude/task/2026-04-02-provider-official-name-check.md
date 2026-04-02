# 2026-04-02 Judge Provider 官方命名核对

## 目标

核对 Judge settings 中可选 provider 的官方命名与接口兼容方式，避免把 MiniMax / Kimi / GLM 之类厂商名称写错或抽象错。

## 检查范围

1. 官方文档中的品牌/平台正式名称
2. 是否提供官方 API
3. 是否明显兼容 OpenAI-compatible
4. 是否适合作为 dashboard provider 显式选项

## 预期输出

1. 建议保留的 provider 枚举
2. 每个 provider 对应的默认 `api_format`
3. 是否需要单独 `base_url` 默认值
4. 哪些应继续归入 `custom`

## 结论

### 建议保留的 provider slug

1. `anthropic`
2. `openai`
3. `openrouter`
4. `minimax`
5. `moonshot`
6. `zai`
7. `custom`

### Dashboard 显示名

1. `Anthropic`
2. `OpenAI`
3. `OpenRouter`
4. `MiniMax`
5. `Moonshot AI (Kimi)`
6. `Z.ai (GLM / 智谱)`
7. `Custom`

### 默认 api_format

1. `anthropic` -> `anthropic`
2. 其他 provider 默认 -> `openai_compatible`

### 默认 base_url

1. `openai` -> `https://api.openai.com/v1`
2. `openrouter` -> `https://openrouter.ai/api/v1`
3. `minimax` -> `https://api.minimax.io/v1`
4. `moonshot` -> `https://api.moonshot.cn/v1`
5. `zai` -> `https://api.z.ai/api/paas/v4/`
6. `anthropic` -> 空，继续走官方默认
7. `custom` -> 用户手填

### 处理原则

1. 不使用 `kimi` 和 `glm` 作为内部 provider slug
2. `Kimi`、`GLM` 仅作为 UI 说明文字出现
3. `custom` 保留为兜底，不替代主流平台显式选项

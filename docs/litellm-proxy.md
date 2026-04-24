# LiteLLM Proxy 接入说明

LiteLLM Proxy 是推荐的统一模型网关方案。它可以把 OpenAI、Claude、Gemini、Azure OpenAI、Ollama、OpenRouter 等模型统一暴露为 OpenAI 输入/输出格式，本项目只需要按 OpenAI-compatible API 调用 LiteLLM 即可。

## 适用场景

- 不希望项目内维护多套模型请求格式。
- 团队需要统一管理多家模型的 Key、预算、限流和 fallback。
- 希望前端只配置一个网关地址，然后通过模型名切换不同供应商。

## 最小启动

安装并启动单模型代理：

```bash
uv tool install "litellm[proxy]"
litellm --model openai/gpt-4.1-mini --host 0.0.0.0 --port 4000
```

如果使用 Docker，可参考 LiteLLM 官方镜像，把配置文件挂载到容器中运行。

## 多模型配置示例

创建 `litellm_config.yaml`：

```yaml
model_list:
  - model_name: gpt-4.1-mini
    litellm_params:
      model: openai/gpt-4.1-mini
      api_key: os.environ/OPENAI_API_KEY

  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-5
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: gemini-flash
    litellm_params:
      model: gemini/gemini-2.5-flash
      api_key: os.environ/GEMINI_API_KEY

  - model_name: qwen-local
    litellm_params:
      model: ollama/qwen3:8b
      api_base: http://localhost:11434

litellm_settings:
  master_key: sk-litellm-local
```

启动：

```bash
litellm --config litellm_config.yaml --host 0.0.0.0 --port 4000
```

## 在本项目中配置

前端左侧模型配置：

- 供应商：`LiteLLM Proxy`
- Base URL：`http://localhost:4000`
- API Key：如果设置了 `master_key`，填 `sk-litellm-local`；否则可留空
- API 协议模式：默认 `自动识别`
- 模型名称：同步模型列表后选择，或手动输入 `model_name`

建议先点击“验证端点”。验证会检查：

1. `/models` 是否可用
2. 最小对话请求是否可用

## API 模式选择

| 模式 | 用途 |
| --- | --- |
| `自动识别` | 推荐默认值；普通模型走 Chat，模型名含 `codex` 时走 Responses |
| `OpenAI Chat` | `/chat/completions`，适合绝大多数 LiteLLM 路由 |
| `OpenAI Responses` | `/responses`，适合 Codex/Responses 类型模型 |
| `Claude Messages` | 仅当 LiteLLM 后面不是统一代理，而是直连 Claude 原生网关时使用 |

## 验收命令

```bash
curl http://localhost:4000/models \
  -H "Authorization: Bearer sk-litellm-local"

curl http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-litellm-local" \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [{"role": "user", "content": "请只回复 OK"}],
    "temperature": 0
  }'
```

如果这两条通过，本项目选择 `LiteLLM Proxy` 后也应能通过“验证端点”。

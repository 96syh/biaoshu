# 本地大模型调用 API 文档

本文档说明如何调用你当前部署在局域网中的本地模型服务，以及如何通过本项目后端接入该模型。

当前已验证可用的本地模型配置：

- `Base URL`: `http://192.168.3.8:8000/v1`
- `API Key`: `dz6120`
- `Model`: `DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ`
- `协议`: OpenAI Compatible API

## 1. 前置条件

调用前请确认本地模型服务满足以下条件：

1. 服务已经启动。
2. 服务监听在 `0.0.0.0:8000` 或实际局域网 IP，而不是只监听 `127.0.0.1:8000`。
3. 当前调用机器可以访问 `192.168.3.8:8000`。
4. 模型服务启用了 OpenAI 兼容接口。

建议先执行以下命令做联通性检查：

```bash
curl -H "Authorization: Bearer dz6120" http://192.168.3.8:8000/v1/models
```

如果返回模型列表，说明服务已可被局域网访问。

## 2. 接口概览

### 2.1 获取模型列表

- 方法：`GET`
- 地址：`/v1/models`
- 完整地址：`http://192.168.3.8:8000/v1/models`

请求示例：

```bash
curl -H "Authorization: Bearer dz6120" \
  http://192.168.3.8:8000/v1/models
```

响应示例：

```json
{
  "object": "list",
  "data": [
    {
      "id": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
      "object": "model",
      "created": 1776089753,
      "owned_by": "omlx"
    }
  ]
}
```

### 2.2 对话补全

- 方法：`POST`
- 地址：`/v1/chat/completions`
- 完整地址：`http://192.168.3.8:8000/v1/chat/completions`
- Content-Type：`application/json`

请求体字段：

- `model`: 模型名，当前使用 `DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ`
- `messages`: 对话消息数组
- `temperature`: 采样温度，结构化任务建议 `0` 到 `0.3`
- `max_tokens`: 最大输出 token 数
- `stream`: 是否流式返回

非流式示例：

```bash
curl http://192.168.3.8:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dz6120" \
  -d '{
    "model": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "messages": [
      {
        "role": "user",
        "content": "请用一句话介绍这个模型。"
      }
    ],
    "temperature": 0.3,
    "max_tokens": 256,
    "stream": false
  }'
```

响应示例：

```json
{
  "id": "chatcmpl-9cf698c1",
  "object": "chat.completion",
  "created": 1776089758,
  "model": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

流式示例：

```bash
curl -N http://192.168.3.8:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dz6120" \
  -d '{
    "model": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "messages": [
      {
        "role": "user",
        "content": "请分三点介绍知识库系统建设方案。"
      }
    ],
    "temperature": 0.3,
    "max_tokens": 512,
    "stream": true
  }'
```

## 3. 代码调用示例

### 3.1 Python 示例

```python
import requests

base_url = "http://192.168.3.8:8000/v1"
api_key = "dz6120"

payload = {
    "model": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "messages": [
        {"role": "system", "content": "你是一个专业的技术方案顾问。"},
        {"role": "user", "content": "请写一个投标系统的技术架构概述。"},
    ],
    "temperature": 0.2,
    "max_tokens": 800,
    "stream": False,
}

response = requests.post(
    f"{base_url}/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json=payload,
    timeout=120,
)

response.raise_for_status()
data = response.json()
print(data["choices"][0]["message"]["content"])
```

### 3.2 JavaScript 示例

```javascript
const response = await fetch("http://192.168.3.8:8000/v1/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer dz6120",
  },
  body: JSON.stringify({
    model: "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    messages: [
      { role: "system", content: "你是一个专业的投标文档助手。" },
      { role: "user", content: "请输出一份项目实施计划的目录。" }
    ],
    temperature: 0.2,
    max_tokens: 800,
    stream: false,
  }),
});

const data = await response.json();
console.log(data.choices[0].message.content);
```

## 4. 通过本项目接入本地模型

如果希望让“华正 AI 标书创作平台”使用这台本地模型，请调用项目后端接口，而不是直接改前端代码。

项目后端默认地址示例：

- `http://127.0.0.1:8090`

### 4.1 保存模型配置

- 方法：`POST`
- 地址：`/api/config/save`

请求示例：

```bash
curl http://127.0.0.1:8090/api/config/save \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "custom",
    "api_key": "dz6120",
    "base_url": "http://192.168.3.8:8000/v1",
    "model_name": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "api_mode": "chat"
  }'
```

### 4.2 验证模型配置

- 方法：`POST`
- 地址：`/api/config/verify`

用途：

- 检查 Base URL 是否可达
- 检查 `/models` 是否正常
- 检查 `/chat/completions` 是否正常
- 返回结构化诊断结果

请求示例：

```bash
curl http://127.0.0.1:8090/api/config/verify \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "custom",
    "api_key": "dz6120",
    "base_url": "http://192.168.3.8:8000/v1",
    "model_name": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "api_mode": "chat"
  }'
```

成功响应示例：

```json
{
  "success": true,
  "message": "模型端点验证通过，可用于当前项目。",
  "provider": "custom",
  "normalized_base_url": "http://192.168.3.8:8000/v1",
  "resolved_base_url": "http://192.168.3.8:8000/v1",
  "base_url_candidates": [
    "http://192.168.3.8:8000/v1"
  ],
  "model_name": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
  "api_mode": "chat",
  "checks": [
    {
      "stage": "models",
      "success": true,
      "detail": "成功获取到 1 个模型",
      "url": "http://192.168.3.8:8000/v1/models",
      "http_status": 200
    },
    {
      "stage": "chat",
      "success": true,
      "detail": "OpenAI 兼容聊天接口调用成功",
      "url": "http://192.168.3.8:8000/v1/chat/completions",
      "http_status": 200,
      "model_name": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ"
    }
  ]
}
```

### 4.3 同步模型列表

- 方法：`POST`
- 地址：`/api/config/models`

请求示例：

```bash
curl http://127.0.0.1:8090/api/config/models \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "custom",
    "api_key": "dz6120",
    "base_url": "http://192.168.3.8:8000/v1",
    "model_name": "DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "api_mode": "chat"
  }'
```

### 4.4 自定义端点协议模式

`provider=custom` 时可以显式指定 `api_mode`，避免后端只靠模型名或失败重试猜测协议：

| api_mode | 适用端点 | 后端调用方式 |
| --- | --- | --- |
| `auto` | 不确定协议的自定义网关 | 优先按 OpenAI Chat；模型名含 `codex` 时走 Responses；失败后尝试 Claude 原生 |
| `chat` | OpenAI-compatible 服务、本地 vLLM/Ollama/LM Studio/DashScope 兼容层 | `/v1/chat/completions` |
| `responses` | OpenAI Responses/Codex 兼容网关 | `/v1/responses` |
| `anthropic` | Claude 原生或兼容网关 | `/v1/messages` 和 `/v1/models` |

前端配置面板中选择“Custom”后，会显示“API 协议模式”。如果你的模型列表接口不可用，也可以直接手动输入模型名，然后点击“验证端点”检查最小对话是否可用。

### 4.5 业务接口调用顺序

如果你要完整跑一遍标书生成链路，建议顺序如下：

1. `POST /api/config/save`
2. `POST /api/config/verify`
3. `POST /api/document/upload`
4. `POST /api/document/analyze-stream`
5. `POST /api/outline/generate-stream`
6. `POST /api/content/generate-chapter-stream`
7. `POST /api/document/export-word`

## 5. 结构化输出建议

这个本地模型当前可以正常返回 OpenAI 兼容结果，但存在一个特点：

- 它可能输出 `<think>` 或较长推理内容

所以在目录生成、JSON 生成、表单抽取这类任务里，建议：

1. `temperature` 使用 `0` 到 `0.3`
2. 优先使用“只输出 JSON”的系统提示词
3. 先用 `stream: false` 调试结构化输出，再切换到流式
4. 如果返回内容混入推理文本，先做内容清洗再解析 JSON

推荐系统提示词示例：

```text
你必须只输出合法 JSON，不要输出 markdown 代码块，不要输出任何解释、前言、结语或思考过程。
```

## 6. 常见问题

### 6.1 本机能通，局域网不通

原因通常是模型服务只监听了 `127.0.0.1`。

正确做法：

```bash
--host 0.0.0.0 --port 8000
```

### 6.2 `/models` 能通，但业务生成很慢

说明接口兼容没问题，但模型推理速度偏慢，常见于：

- 模型较大
- CPU 推理
- 量化模型首 token 时间较长
- reasoning 模型默认会先生成思考内容

### 6.3 `chat/completions` 返回 200，但 JSON 解析失败

说明模型有输出，但没有严格遵守结构化格式。请收紧提示词，并降低温度。

## 7. 推荐验收命令

```bash
# 1. 检查模型列表
curl -H "Authorization: Bearer dz6120" \
  http://192.168.3.8:8000/v1/models

# 2. 检查最小对话
curl http://192.168.3.8:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dz6120" \
  -d '{
    "model":"DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "messages":[{"role":"user","content":"请只回复OK"}],
    "temperature":0,
    "max_tokens":16,
    "stream":false
  }'

# 3. 检查项目接入
curl http://127.0.0.1:8090/api/config/verify \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"custom",
    "api_key":"dz6120",
    "base_url":"http://192.168.3.8:8000/v1",
    "model_name":"DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ",
    "api_mode":"chat"
  }'
```

当这三步都通过时，说明“本地模型服务”和“标书项目接入链路”都已经可用。

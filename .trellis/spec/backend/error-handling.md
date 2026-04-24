# Error Handling

> How errors are handled in this project.

---

## Overview

Backend errors are handled with FastAPI `HTTPException` for request-level
failures and structured JSON/SSE payloads for long-running AI operations. User
messages should be in Simplified Chinese. Routers should preserve intentional
`HTTPException`s and wrap unexpected exceptions with a domain-specific Chinese
message.

---

## Error Types

The project currently does not define custom exception classes. Existing
patterns are:

- `HTTPException(status_code=400, detail=...)` for invalid auth/config.
- `HTTPException(status_code=500, detail=...)` for unexpected request failures.
- SSE payloads such as `{"error": true, "message": "..."}` or
  `{"status": "error", "message": "..."}` for streaming endpoints.
- Pydantic response models such as `ConfigResponse`, `ModelListResponse`, and
  `ProviderVerifyResponse` for non-streaming structured responses.

---

## Error Handling Patterns

Follow these patterns:

- Check provider auth before creating model requests:
  `get_provider_auth_error(config.get("provider"), config.get("api_key"))`.
- Re-raise `HTTPException` unchanged in outer `except HTTPException` blocks.
- For SSE endpoints, catch model/service errors inside the generator and emit
  an error event before `[DONE]`.
- Preserve underlying exception text when it helps users fix provider
  configuration, model names, quota, or Base URL issues.
- For file upload validation, return a normal response with `success=False`
  when the frontend expects a typed upload response.

---

## API Error Responses

API response examples:

```json
{"success": false, "message": "当前供应商需要先输入 API Key"}
```

```json
{"error": true, "message": "文档分析失败: ..."}
```

```json
{"status": "error", "message": "模型返回空内容，可能是配额限制、内容拦截或兼容模式异常"}
```

Streaming endpoints must always finish with:

```text
data: [DONE]
```

---

## Common Mistakes

Avoid:

- Returning English-only user-facing errors.
- Raising inside an SSE generator without sending a final error payload.
- Swallowing provider endpoint/model errors into a generic "failed" message.
- Logging or returning raw API keys, full uploaded files, or customer-sensitive
  content in errors.
- Changing an API error shape without updating `frontend/src/services/api.ts`
  and the consuming page.

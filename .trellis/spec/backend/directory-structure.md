# Directory Structure

> How backend code is organized in this project.

---

## Overview

The backend is a FastAPI application under `backend/app`. API endpoints live in
routers, business logic lives in services, request/response contracts live in
Pydantic models, and reusable helpers live in utils. Keep endpoint functions
thin: validate auth/config, construct service calls, stream or return a
response, and convert exceptions into Chinese user-facing messages.

---

## Directory Layout

```
backend/
├── run.py                         # local uvicorn launcher
├── requirements.txt               # full local/backend dependency set
├── requirements.docker.txt        # slim Docker runtime dependency set
├── requirements-cloudflare.txt    # Cloudflare/container dependency set
└── app/
    ├── main.py                    # FastAPI app, CORS, routers, static frontend
    ├── config.py                  # application settings
    ├── models/
    │   └── schemas.py             # Pydantic API contracts
    ├── routers/
    │   ├── config.py              # model provider config and verification
    │   ├── document.py            # upload, analysis, Word export
    │   ├── outline.py             # outline generation SSE APIs
    │   ├── content.py             # chapter content generation APIs
    │   ├── expand.py              # existing-plan outline extraction
    │   └── search.py              # optional search router
    ├── services/
    │   ├── openai_service.py      # multi-provider AI compatibility layer
    │   ├── file_service.py        # upload/text/image extraction
    │   └── search_service.py      # optional web search implementation
    └── utils/
        ├── config_manager.py      # ~/.ai_write_helper/user_config.json
        ├── provider_registry.py   # provider defaults and URL normalization
        ├── prompt_manager.py      # reusable prompt builders
        ├── json_util.py           # JSON schema checking
        ├── outline_util.py        # outline node distribution helpers
        └── sse.py                 # shared StreamingResponse wrapper
```

---

## Module Organization

Use the existing layer boundaries:

- Add or change API endpoints in `backend/app/routers/<feature>.py`.
- Put long-running, provider-specific, or document-processing logic in
  `backend/app/services/`.
- Put cross-router helpers in `backend/app/utils/`.
- Add or update Pydantic contracts in `backend/app/models/schemas.py`.
- Register new routers in `backend/app/main.py`.
- Keep prompt text in `prompt_manager.py` when it is shared or reusable; local
  one-off prompts may stay near the service/router that owns them.
- If adding a dependency, update every relevant requirement/build surface:
  `backend/requirements.txt`, `backend/requirements.docker.txt` if needed,
  `backend/requirements-cloudflare.txt` if needed, and `build.py` when the exe
  bundle needs it.

---

## Naming Conventions

Use lowercase snake_case for Python files and modules. Router files should be
named after the API domain (`document.py`, `outline.py`, `content.py`). Service
classes use PascalCase (`OpenAIService`, `FileService`), while route functions
and helpers use snake_case.

---

## Examples

Good examples:

- `backend/app/routers/content.py`: thin FastAPI router that delegates chapter
  generation to `OpenAIService` and streams structured SSE events.
- `backend/app/utils/sse.py`: shared wrapper for consistent SSE headers.
- `backend/app/utils/provider_registry.py`: central provider metadata instead
  of scattered provider-specific constants.

Avoid:

- Adding provider-specific constants directly inside UI-facing routers.
- Putting large AI orchestration or document parsing blocks in route handlers.
- Registering heavy optional routers unconditionally; follow the
  `ENABLE_SEARCH_ROUTER` pattern in `backend/app/main.py`.

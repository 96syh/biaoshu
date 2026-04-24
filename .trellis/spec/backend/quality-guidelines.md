# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

Backend quality is defined by stable API contracts, reliable SSE streaming,
provider compatibility, safe document handling, and deployability across local,
Docker, and exe builds. Prefer small targeted changes and verify the exact
route/service touched.

---

## Forbidden Patterns

Forbidden patterns:

- Hardcoding API keys, provider credentials, customer data, or local-only model
  URLs in source files.
- Concatenating untrusted input into shell commands.
- Adding heavyweight optional search/browser dependencies to the slim Docker
  runtime unless the search router is intentionally enabled.
- Changing Pydantic schema field names without updating frontend TypeScript
  interfaces and consumers.
- Returning malformed SSE frames or omitting the `[DONE]` sentinel.
- Letting model-generated JSON pass to the frontend without extraction and
  validation when the route expects JSON.

---

## Required Patterns

Required patterns:

- Use `sse_response(...)` for SSE endpoints.
- Use `config_manager.load_config()` and provider registry helpers for
  provider auth, Base URL normalization, and default models.
- Keep upload type checks aligned between backend `FileService` and frontend
  upload UI messages.
- Use `ensure_ascii=False` for JSON sent to the frontend when Chinese text is
  expected.
- When adding dependencies, update requirement/build surfaces consistently.
- For AI-generated structured data, use `_extract_json_payload(...)` and
  `check_json(...)` or equivalent validation before parsing.

---

## Testing Requirements

Testing depends on change risk:

- Router or schema change: run backend import/smoke checks and verify FastAPI
  docs or route behavior.
- Provider compatibility change: verify at least one configured provider or a
  mocked/local OpenAI-compatible endpoint; report any missing API key honestly.
- Document parsing change: test PDF and DOCX paths when possible.
- Word export change: generate a sample DOCX and inspect that headings/body
  render correctly.
- Dependency/build change: run the relevant build command (`npm run build`,
  Docker build, or `python build.py`) when feasible.

---

## Code Review Checklist

Review checklist:

- Does the API response shape still match `frontend/src/services/api.ts`?
- Are Chinese user-facing messages preserved?
- Are provider-specific paths centralized in `provider_registry.py` or
  `OpenAIService`, not spread across routers?
- Are uploaded files cleaned up and unsupported `.doc` uploads rejected?
- Are secrets and sensitive tender content kept out of logs and source files?
- Does the change work for both streaming and non-streaming paths when both
  exist?

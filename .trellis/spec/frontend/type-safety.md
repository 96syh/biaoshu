# Type Safety

> Type safety patterns in this project.

---

## Overview

The frontend uses TypeScript with `strict: true` in `frontend/tsconfig.json`.
Shared app/domain types live in `frontend/src/types/index.ts`; API-specific
request/response interfaces live in `frontend/src/services/api.ts`. Runtime
validation is mostly manual, especially for streamed SSE payloads and
model-generated JSON.

---

## Type Organization

Type organization:

- Shared domain/application types: `types/index.ts`.
- API payload interfaces: `services/api.ts`.
- Component-only props and helper interfaces: inside the component file.
- Backend contract source of truth: `backend/app/models/schemas.py`; keep
  frontend interfaces aligned with Pydantic schemas.

---

## Validation

No runtime validation library is used. Existing validation patterns are:

- Backend validates API requests with Pydantic.
- Frontend validates upload extensions before sending files.
- SSE consumers check payload flags/status fields before using content.
- Outline JSON is parsed through `extractJsonPayload(...)` before
  `JSON.parse(...)`.

---

## Common Patterns

Common patterns:

- Use discriminated string values for known modes, for example
  `analysis_type: 'overview' | 'requirements'`.
- Use explicit interfaces for provider verification payloads.
- Prefer `OutlineData` and `OutlineItem` from shared types over `any`.
- Keep nullable values explicit with `null` or optional fields.

---

## Forbidden Patterns

Avoid:

- Introducing new `any` fields when the backend schema is known.
- Changing API interfaces only on the frontend or only on the backend.
- Assuming every SSE payload has the same shape; `document`, `outline`, and
  `content` streams use different fields.
- Type assertions that hide missing/null content from model responses.

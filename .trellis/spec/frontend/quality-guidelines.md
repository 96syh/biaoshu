# Quality Guidelines

> Code quality standards for frontend development.

---

## Overview

Frontend quality depends on preserving the three-step workflow, keeping API
contracts aligned with FastAPI, handling SSE failures clearly, and maintaining a
usable Chinese console UI. The app uses Create React App scripts.

---

## Forbidden Patterns

Forbidden patterns:

- Hardcoding production API URLs when `REACT_APP_API_URL` or
  `window.location.origin` should be used.
- Duplicating API endpoint paths outside `services/api.ts`.
- Ignoring SSE error payloads or `[DONE]` events.
- Letting generated content overwrite unrelated chapter ids.
- Adding new visible English UI copy in the main workflow unless it is already
  part of the design language.
- Storing API keys in frontend source or local files.

---

## Required Patterns

Required patterns:

- Use `consumeSseStream(...)` for streaming endpoints.
- Use `draftStorage` helpers for draft/generated content persistence.
- Normalize model/provider errors into clear Chinese messages where users need
  to switch keys, providers, or models.
- Keep file upload validation consistent with backend `.pdf`/`.docx` support
  and `.doc` rejection.
- Use existing button/panel/workspace classes before adding new visual systems.

---

## Testing Requirements

Testing expectations:

- Run `npm run build` for UI, API interface, or TypeScript changes.
- Run `npm test -- --watchAll=false` when changing testable component behavior.
- For SSE or model workflow changes, manually test at least the affected step
  with a reachable backend or document why it could not be tested.
- For export changes, generate and inspect a DOCX.

---

## Code Review Checklist

Review checklist:

- Does the page still block invalid step actions with clear messages?
- Are streaming buffers cleared on success and failure?
- Are backend schema changes reflected in `services/api.ts` and shared types?
- Are upload, quota, empty-response, and parse-failure states handled?
- Does the UI remain usable on the app's desktop console layout?

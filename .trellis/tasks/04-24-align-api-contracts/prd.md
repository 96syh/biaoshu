# Align Frontend and Backend API Contracts

## Goal

Ensure Pydantic schemas, TypeScript interfaces, and actual endpoint payloads
match across the application.

## Scope

- Compare `backend/app/models/schemas.py` with
  `frontend/src/services/api.ts` and `frontend/src/types/index.ts`.
- Document or fix mismatches for config, provider verification, upload,
  analysis, outline, content generation, and export.
- Include SSE payload shapes for document, outline, and content streams.

## Deliverables

- Contract inventory or patch.
- Any needed type updates.
- Notes about intentionally loose `any` fields that should become typed later.

## Validation

- Run `npm run build`.
- Run backend import checks.
- If code changes are made, verify affected API consumers.

# Extract Full-Bid Prompt Rules Into Structured Workflow

## Goal

Fold the external full-bid prompt template into the existing structured prompt workflow without replacing the staged JSON-first architecture.

## Scope

- Extend `AnalysisReport` with complete-bid structure, review, scoring, price, fixed-format, signature, and evidence-chain fields.
- Extend `ReviewReport` with fixed-format, signature, price-rule, evidence-chain, and page-reference checks.
- Add reusable prompt rule fragments so analysis, chapter generation, and compliance review share the same business constraints.
- Keep old flows compatible through default empty Pydantic fields and optional frontend typing.

## Acceptance

- Backend Pydantic and frontend TypeScript contracts stay aligned.
- Structured model outputs remain JSON-only and Pydantic-validated.
- Frontend production build succeeds.
- No new dependency or runtime configuration is introduced.

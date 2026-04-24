# Run End-to-End Smoke Verification

## Goal

Verify the main bid-generation workflow from configuration through Word export.

## Scope

- Backend startup and health/docs checks.
- Frontend build or local app availability.
- Model configuration load/save/verify path.
- File upload and document text extraction.
- Analysis, outline generation, chapter generation, and Word export.

## Constraints

- Do not expose or commit API keys.
- If a real model key is unavailable, run all non-model checks and clearly
  mark model-dependent steps as blocked.

## Validation

- Run backend import/startup checks.
- Run `npm run build` for frontend TypeScript/build validation.
- Run API smoke checks where credentials and sample files permit.
- Save exact commands, outputs, and blockers.

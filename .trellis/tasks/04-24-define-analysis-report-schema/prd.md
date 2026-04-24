# Define AnalysisReport Schema

## Goal

Add explicit data contracts for the structured standard analysis report and
review-ready prompt workflow.

## Scope

- Add backend Pydantic types for `BidMode`, `AnalysisReport`, scoring items,
  qualification requirements, formal response requirements, mandatory clauses,
  rejection risks, required materials, and missing company materials.
- Add matching frontend TypeScript types.
- Extend `OutlineItem` only if this task is chosen to include mapping fields;
  otherwise leave outline mapping to `map-outline-to-requirements`.

## References

- `docs/prompt-workflow.md`
- `backend/app/models/schemas.py`
- `frontend/src/types/index.ts`
- `frontend/src/services/api.ts`

## Validation

- Run backend import checks.
- Run `npm run build`.
- Confirm old request/response fields remain compatible.

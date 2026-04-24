# Map Outline Nodes to Requirements

## Goal

Extend outline generation so each outline node can be traced back to scoring
items, requirements, risks, and materials from `AnalysisReport`.

## Scope

- Add mapping fields to outline contracts.
- Update level-1 outline generation to produce mapping ids.
- Update level-2/level-3 expansion to preserve and refine mapping ids.
- Preserve frontend tree editing behavior.

## References

- `docs/prompt-workflow.md`
- `backend/app/services/openai_service.py`
- `backend/app/utils/outline_util.py`
- `frontend/src/pages/OutlineEdit.tsx`

## Validation

- Run JSON schema/extraction checks.
- Run `npm run build` if TypeScript contracts change.
- Confirm every technical scoring item can be associated with at least one
  outline node in a sample run.

# Add Compliance Review Step

## Goal

Add a pre-export review stage that checks the generated bid content before Word
export.

## Scope

- Add `ReviewReport` contracts.
- Add a compliance review prompt and endpoint.
- Check scoring coverage, missing materials, rejection risks, duplicate
  content, and fabrication risk.
- Surface blocking issues before export in the frontend.

## References

- `docs/prompt-workflow.md`
- `backend/app/routers/document.py`
- `backend/app/services/openai_service.py`
- `frontend/src/pages/ContentEdit.tsx`

## Validation

- Run backend import checks.
- Run `npm run build`.
- Test review on a small generated outline/content sample.

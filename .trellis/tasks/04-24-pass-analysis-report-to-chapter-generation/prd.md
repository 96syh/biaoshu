# Pass AnalysisReport Into Chapter Generation

## Goal

Make chapter generation use the structured analysis report instead of relying
only on project overview, current chapter, parent chapters, and sibling
chapters.

## Scope

- Extend chapter generation request contracts.
- Include `analysis_report`, `bid_mode`, generated summaries, enterprise
  materials, and missing materials in the generation context.
- Update the chapter prompt to ground writing in mapped scoring/material ids.
- Preserve existing chapter generation API compatibility where practical.

## References

- `docs/prompt-workflow.md`
- `backend/app/routers/content.py`
- `backend/app/services/openai_service.py`
- `frontend/src/pages/ContentEdit.tsx`

## Validation

- Run backend import checks.
- Run `npm run build`.
- Verify missing material placeholders originate from `AnalysisReport`.

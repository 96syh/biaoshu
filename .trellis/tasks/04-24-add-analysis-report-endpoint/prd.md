# Add Structured Analysis Report Endpoint

## Goal

Add a model endpoint that converts tender text into `AnalysisReport JSON`.

## Scope

- Add a prompt builder for AnalysisReport generation.
- Add a streaming endpoint such as `/api/document/analyze-report-stream`.
- Use existing JSON extraction and schema validation patterns.
- Keep current overview/requirements analysis paths working.

## References

- `docs/prompt-workflow.md`
- `backend/app/routers/document.py`
- `backend/app/services/openai_service.py`
- `backend/app/utils/prompt_manager.py`

## Validation

- Run backend import checks.
- Verify SSE emits JSON chunks and `[DONE]`.
- Test with a small sample tender text when model access is available.

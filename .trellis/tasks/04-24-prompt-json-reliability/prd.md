# Harden Prompt and JSON Output Reliability

## Goal

Improve reliability for prompt-driven outline/content generation across OpenAI
compatible providers and local models.

## Scope

- Review prompt boundaries in `backend/app/utils/prompt_manager.py` and
  `backend/app/services/openai_service.py`.
- Review JSON extraction, schema checking, retry behavior, and SSE output.
- Check frontend outline JSON parsing behavior in `OutlineEdit.tsx`.
- Preserve existing provider compatibility behavior.

## Risks

- Prompt changes can alter generated bid structure.
- JSON schema changes can break frontend parsing.
- Local models may ignore `response_format`.

## Validation

- Add or run focused tests/scripts if available.
- At minimum, run Python import checks and a mocked/local JSON extraction
  verification.
- Run frontend build if TypeScript parsing code changes.

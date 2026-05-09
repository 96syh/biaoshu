# Audit Current Uncommitted Business Changes

## Goal

Separate pre-existing business changes from Trellis initialization files and
produce a clean review/commit plan.

## Scope

- Inspect `git status`, `git diff --stat`, and focused diffs for modified
  business files.
- Identify which changes belong to model-provider support, prompt/outline
  generation, docs, and Trellis initialization.
- Do not revert or overwrite user changes.

## Deliverables

- A concise change inventory grouped by area.
- Risk notes for large or high-impact diffs.
- Recommended commit or review order.

## Validation

- Run `git status --short`.
- Run targeted `git diff -- <file>` reads for each modified business file.
- Report exact commands reviewed.

## Remediation Addendum

This task also covers the follow-up fixes from the review of the current
uncommitted changes. The goal is to keep the existing product behavior while
removing correctness, reliability, test, and documentation risks.

### Findings Addressed

- Draft persistence pressure: streaming chapter generation must not write the
  full active draft JSON to the backend SQLite database for every chunk. The
  frontend may update the live preview on each chunk, but persisted draft saves
  must be coalesced/debounced and flushed at final commit points.
- Bid mode contract drift: frontend `BidMode` values must stay aligned with
  `backend/app/models/schemas.py::BidMode`. Normalization may accept known
  aliases, but it must not silently downgrade backend-supported modes such as
  `service_plan`, `construction_plan`, `goods_supply_plan`,
  `business_volume`, `qualification_volume`, or `price_volume`.
- Frontend test entry: the CRA/Jest smoke test must render the current
  workspace shell and mock ESM-only or network-facing modules as needed.
- Local model documentation: tracked docs must use placeholders or environment
  variables for model endpoint, API key, and model id. Real internal endpoints
  and keys must be rotated if they were previously committed.

### Expected Verification

- `cd frontend && ./node_modules/.bin/tsc --noEmit --pretty false`
- `cd frontend && npm run test -- --watchAll=false`
- `cd frontend && npm run build`
- `cd backend && ../.venv311/bin/python -c "import app.main; print('backend_import_ok')"`
- `rg -n "dz6120|192\\.168\\.3\\.8|DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ" docs/local-model-api.md`

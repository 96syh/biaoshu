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

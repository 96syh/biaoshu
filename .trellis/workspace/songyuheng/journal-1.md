# Journal - songyuheng (Part 1)

> AI development session journal
> Started: 2026-04-24

---



## Session 1: Bootstrap Trellis guidelines and task queue

**Date**: 2026-04-24
**Task**: Bootstrap Trellis guidelines and task queue
**Branch**: `master`

### Summary

Filled backend/frontend Trellis specs from the existing FastAPI and React codebase, archived the bootstrap task, and created planning tasks for review, smoke verification, prompt reliability, API contracts, deployment validation, and Codex hooks.

### Main Changes

(Add details)

### Git Commits

(No commits - planning session)

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: Fix review findings for draft persistence, bid modes, tests, and docs

**Date**: 2026-05-05
**Task**: Fix four review findings from the current uncommitted changes
**Branch**: `master`

### Summary

Resolved the follow-up findings by coalescing large draft persistence during
streaming generation, preserving all backend-supported bid generation modes in
the frontend, replacing the broken default CRA test with a current workspace
smoke test, and sanitizing local model documentation so tracked docs no longer
contain internal endpoint or API key examples.

### Main Changes

- Added debounced draft saves with explicit flush points after final chapter and
  batch generation commits.
- Expanded frontend `BidMode` to match the backend enum and replaced the
  two-button mode selector with a compact selector covering specialized modes.
- Mocked ESM/network-facing frontend dependencies in Jest and asserted the
  current local workspace shell.
- Updated local model, README, and Trellis docs with the new persistence,
  BidMode, testing, and secret-handling constraints.

### Git Commits

(No commits - remediation session)

### Testing

- [OK] `cd frontend && ./node_modules/.bin/tsc --noEmit --pretty false`
- [OK] `cd frontend && npm run test -- --watchAll=false`
- [OK] `cd frontend && npm run build`
- [OK] `cd backend && ../.venv311/bin/python -c "import app.main; print('backend_import_ok')"`
- [OK] `rg -n "dz6120|192\\.168\\.3\\.8|DeepSeek-R1-0528-Qwen3-8B-4bit-AWQ" .`

### Status

[OK] **Completed**

### Next Steps

- Rotate any real model key that may have been committed before this cleanup.


## Session 2: Document prompt workflow optimization

**Date**: 2026-04-24
**Task**: Document prompt workflow optimization
**Branch**: `master`

### Summary

Added docs/prompt-workflow.md to capture the current prompt chain, the optimized six-stage workflow, structured JSON contracts, prompt template guidance, migration order, and Trellis child tasks for implementation.

### Main Changes

(Add details)

### Git Commits

(No commits - planning session)

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: Define AnalysisReport schema contracts

**Date**: 2026-04-24
**Task**: Define AnalysisReport schema contracts
**Branch**: `master`

### Summary

Added AnalysisReport and BidMode contracts to backend Pydantic schemas and matching frontend TypeScript types, with API type re-exports for future structured analysis endpoint work. Verified backend import using Anaconda Python and frontend production build.

### Main Changes

(Add details)

### Git Commits

(No commits - planning session)

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: 端到端 smoke 与解析兜底

**Date**: 2026-04-25
**Task**: 端到端 smoke 与解析兜底
**Branch**: `master`

### Summary

修复结构化解析长 JSON 超时；增加本地兜底解析、目录、正文、审校与安全验证模式；使用福建招标文件跑通上传到 Word 导出链路。

### Main Changes

(Add details)

### Git Commits

(No commits - planning session)

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete

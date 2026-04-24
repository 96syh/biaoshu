# Directory Structure

> How frontend code is organized in this project.

---

## Overview

The frontend is organized by UI role rather than deep feature folders. The
top-level `App.tsx` owns the three-step workflow shell, pages implement each
workflow step, components are reusable UI pieces, services wrap HTTP/SSE APIs,
hooks own app-level state, and utils hold browser helpers.

---

## Directory Layout

```
frontend/src/
├── App.tsx                       # shell and step routing
├── App.css                       # app shell and custom UI styles
├── index.css                     # Tailwind/global styles
├── components/
│   ├── ConfigPanel.tsx           # provider/model configuration panel
│   └── StepBar.tsx               # three-step progress navigation
├── constants/
│   └── providers.ts              # provider presets and defaults
├── hooks/
│   └── useAppState.ts            # app workflow state
├── pages/
│   ├── DocumentAnalysis.tsx      # upload and AI analysis
│   ├── OutlineEdit.tsx           # outline generation/editing
│   └── ContentEdit.tsx           # chapter generation and export
├── services/
│   └── api.ts                    # Axios client and fetch-based SSE calls
├── types/
│   └── index.ts                  # shared app/domain types
└── utils/
    ├── draftStorage.ts           # localStorage draft/content helpers
    └── sse.ts                    # SSE stream consumer
```

---

## Module Organization

Place new code by responsibility:

- Page-specific UI and handlers stay in `pages/<Page>.tsx`.
- Reusable visual controls go in `components/`.
- HTTP functions and request/response interfaces go in `services/api.ts`.
- Shared app/domain interfaces go in `types/index.ts`.
- Provider metadata belongs in `constants/providers.ts`.
- Browser-only helpers such as localStorage or stream parsing belong in
  `utils/`.
- App-wide workflow state belongs in `hooks/useAppState.ts` unless a new hook
  is clearly reusable.

---

## Naming Conventions

Use PascalCase for React component/page files and camelCase for hooks, utils,
and constants files. Keep UI copy in Simplified Chinese. Keep TypeScript
interfaces in English.

---

## Examples

Good examples:

- `frontend/src/services/api.ts`: single place for endpoint paths and API
  payload interfaces.
- `frontend/src/utils/sse.ts`: shared SSE parsing instead of reimplementing
  stream parsing in every page.
- `frontend/src/hooks/useAppState.ts`: small app-state hook with focused update
  functions.

Avoid:

- Calling backend URLs directly from multiple components when the call belongs
  in `services/api.ts`.
- Duplicating upload format validation messages across new files.
- Adding unrelated state or handlers to `App.tsx`; keep step details inside
  their page component.

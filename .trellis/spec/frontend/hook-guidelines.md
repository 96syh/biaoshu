# Hook Guidelines

> How hooks are used in this project.

---

## Overview

The main custom hook is `useAppState`, which owns app-wide workflow state for
the three-step bid generation flow. Page components use local React state for
page-specific UI flags, progress, uploaded files, streaming content, and edit
forms.

---

## Custom Hook Patterns

Create a custom hook only when stateful logic is reused or clearly app-wide.
Return state plus named update functions. Use `useCallback` for update
functions passed through props or reused in dependency arrays, as
`useAppState.ts` and `ContentEdit.tsx` do.

---

## Data Fetching

There is no React Query/SWR layer. Data fetching is handled directly in page
event handlers through `services/api.ts`. Standard JSON APIs use Axios; SSE
streaming endpoints use `fetch(...)` plus `consumeSseStream(...)`.

---

## Naming Conventions

Hooks must start with `use`. Hook files use camelCase names, for example
`useAppState.ts`. Hook return values should use explicit names such as
`updateConfig`, `updateOutline`, `nextStep`, and `prevStep`.

---

## Common Mistakes

Avoid:

- Adding server calls to `useAppState`; it should coordinate app state, not own
  backend interactions.
- Storing `Set` or complex mutable objects in state without cloning before
  update.
- Missing dependencies in `useCallback`/`useEffect` when a callback reads props
  or state.
- Rehydrating stale localStorage drafts when the current behavior intentionally
  starts from a fresh workspace on page refresh.

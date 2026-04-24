# Component Guidelines

> How components are built in this project.

---

## Overview

Components are functional React components written in TypeScript. Page
components own workflow-specific state and handlers. Reusable components receive
typed props and callbacks from parents. UI text is Simplified Chinese, with a
professional console/workspace tone.

---

## Component Structure

Typical structure:

1. Imports.
2. Local interfaces for props and local helper types.
3. Small pure helpers/constants.
4. `const Component: React.FC<Props> = (...) => { ... }`.
5. Event handlers and render helpers before JSX return.
6. `export default Component`.

Examples: `ConfigPanel.tsx`, `StepBar.tsx`, `DocumentAnalysis.tsx`.

---

## Props Conventions

Define explicit prop interfaces near the component. Callback props should use
specific argument types, not `Function`. Reuse shared domain types from
`frontend/src/types/index.ts` when passing `OutlineData`, `OutlineItem`, or
configuration structures.

---

## Styling Patterns

Styling uses a mix of Tailwind utility classes and project CSS classes from
`App.css`/`index.css`. Follow existing classes such as `workspace-shell`,
`workspace-intro`, `surface-panel`, `primary-button`, and `secondary-button`.
Use Heroicons for existing icon style consistency.

---

## Accessibility

Required accessibility patterns:

- File inputs may be visually hidden, but must remain connected to a button or
  clickable area through refs/labels.
- Buttons must have clear visible text or a descriptive `title` for icon-only
  actions.
- Disabled states must be explicit for invalid workflow steps.
- Do not rely only on color for success/error state; include text messages.

---

## Common Mistakes

Avoid:

- Large new page components that duplicate existing `DocumentAnalysis`,
  `OutlineEdit`, or `ContentEdit` logic.
- Icon-only controls without `title` or accessible text.
- Introducing a new UI library for a single control.
- Moving API calls into deeply nested child components when the page needs to
  coordinate workflow state.

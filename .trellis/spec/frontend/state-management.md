# State Management

> How state is managed in this project.

---

## Overview

State is managed with React `useState`/`useCallback`; there is no Redux,
Zustand, React Query, or global store. App-wide workflow state is centralized in
`useAppState`. Page-local UI state stays in page components.

---

## State Categories

State categories:

- App workflow state: `currentStep`, model config, file content, analysis
  results, outline data, and selected chapter in `useAppState`.
- Page UI state: loading flags, messages, expanded outline nodes, edit forms,
  progress counters, streaming buffers.
- Persisted draft state: `draftStorage` for selected workflow fields and
  generated chapter content.
- Server state: fetched on demand by event handlers; not globally cached.
- URL state: not used for workflow state.

---

## When to Use Global State

Promote state to `useAppState` only when multiple workflow steps need it or it
must survive step navigation. Keep state local when it only affects a single
page or transient UI behavior.

---

## Server State

Server data is synchronized manually:

- Upload returns extracted file content and stores it in app state.
- Analysis streams accumulate into local buffers, then commit final overview and
  requirements to app state.
- Outline generation streams JSON text, then parses and commits `outlineData`.
- Chapter generation streams content and writes per-chapter content into
  `draftStorage` as it arrives.

---

## Common Mistakes

Avoid:

- Mutating outline or leaf item arrays in place; clone before updating.
- Letting stale generated content survive after uploading a new tender file.
- Treating `draftStorage` as authoritative after the outline changes; filter
  cached content by current leaf node ids.
- Advancing steps automatically before required source data exists.

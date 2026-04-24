# Frontend Development Guidelines

> Best practices for frontend development in this project.

---

## Overview

This directory documents the actual frontend conventions used by the React
proposal-writing console. The frontend is a Create React App TypeScript app
with Tailwind/CSS styling, a three-step workspace, typed API wrappers, SSE
consumption utilities, and browser localStorage draft helpers.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Component Guidelines](./component-guidelines.md) | Component patterns, props, composition | Filled |
| [Hook Guidelines](./hook-guidelines.md) | Custom hooks, data fetching patterns | Filled |
| [State Management](./state-management.md) | Local state, global state, server state | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Type Safety](./type-safety.md) | Type patterns, validation | Filled |

---

## Pre-Development Checklist

Before changing frontend code:

1. Read [Directory Structure](./directory-structure.md).
2. If changing UI, read [Component Guidelines](./component-guidelines.md) and [Quality Guidelines](./quality-guidelines.md).
3. If changing app-wide workflow data, read [State Management](./state-management.md).
4. If changing API calls or payloads, read [Type Safety](./type-safety.md) and the backend specs.
5. If adding shared stateful logic, read [Hook Guidelines](./hook-guidelines.md).

---

**Language**: All documentation should be written in **English**.

# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory documents the actual backend conventions used by this FastAPI
proposal-writing application. Backend work is centered on API routers,
service classes, Pydantic schemas, utility modules, SSE streaming, and
deployment/build scripts. There is currently no database layer.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Database Guidelines](./database-guidelines.md) | Persistence status and future database rules | Filled |
| [Error Handling](./error-handling.md) | Error types, handling strategies | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Logging Guidelines](./logging-guidelines.md) | Logging and sensitive-data rules | Filled |

---

## Pre-Development Checklist

Before changing backend code:

1. Read [Directory Structure](./directory-structure.md).
2. If adding/changing an endpoint, read [Error Handling](./error-handling.md).
3. If touching model providers, prompt flow, streaming, or document parsing, read [Quality Guidelines](./quality-guidelines.md).
4. If adding persistence, read [Database Guidelines](./database-guidelines.md) first because this project currently has no DB.
5. If adding logs, read [Logging Guidelines](./logging-guidelines.md).

---

**Language**: All documentation should be written in **English**.

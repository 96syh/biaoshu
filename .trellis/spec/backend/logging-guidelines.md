# Logging Guidelines

> How logging is done in this project.

---

## Overview

The backend currently uses lightweight `print(...)` logging rather than a
configured structured logging framework. This is acceptable for local/demo
deployment, but logs must remain concise and must not expose secrets or tender
content.

---

## Log Levels

There are no formal log levels yet. Use message prefixes or clear wording:

- Informational: startup/optional-router status, current outline chapter being
  processed.
- Warning: optional dependency unavailable, non-fatal cleanup failure, fallback
  provider model list.
- Error: failed document parsing, failed image extraction, JSON validation
  failure after retries, provider verification failure.

---

## Structured Logging

No structured log schema exists. If adding one, keep logs single-line where
possible and include only non-sensitive context such as route/action,
provider id, stage, and short error text.

---

## What to Log

Useful events:

- Optional search router disabled or failed import in `backend/app/main.py`.
- Advanced document processing libraries unavailable in
  `backend/app/services/file_service.py`.
- JSON schema validation retries in `backend/app/services/openai_service.py`.
- Current top-level outline section during concurrent outline expansion.
- File cleanup failures after upload processing.

---

## What NOT to Log

Never log:

- API keys or Authorization headers.
- Full uploaded tender documents.
- Full generated bid content.
- Customer names, phone numbers, IDs, certificate numbers, invoice data, or
  contract details unless explicitly redacted.
- Raw provider request/response bodies that may contain customer data.

# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

This project currently has no database, ORM, migration framework, or SQL query
layer. Runtime configuration is stored as JSON in the user's home directory via
`backend/app/utils/config_manager.py`. Uploaded files are saved under the
configured upload directory and are treated as filesystem artifacts, not
database records.

---

## Query Patterns

There are no query patterns today. Do not introduce ad hoc SQL or a persistence
library inside routers. If persistence becomes necessary, create a dedicated
data-access layer and update this guide before implementation.

---

## Migrations

No migrations exist. Any future database work must include:

- An explicit migration tool decision.
- A schema/migration directory.
- Local setup and rollback instructions.
- Tests or a smoke script that validates a fresh database.

---

## Naming Conventions

Not applicable yet. For future work, prefer snake_case table and column names,
clear foreign-key names, and migration filenames that include a timestamp and a
short verb phrase.

---

## Common Mistakes

Common mistakes to avoid:

- Treating `~/.ai_write_helper/user_config.json` as a multi-user datastore. It
  is local process/user configuration only.
- Storing API keys, uploaded tender files, generated content, or customer data
  in source-controlled files.
- Adding persistent state without documenting backup, restore, and migration
  behavior for Docker and exe deployments.

# Enable Codex Trellis Hooks

## Goal

Enable Codex UI to automatically load Trellis project context on session start.

## Scope

- Inspect `~/.codex/config.toml`.
- Add `codex_hooks = true` under `[features]` only after explicit approval,
  because this changes global Codex behavior.
- Restart Codex UI or instruct the user to restart if the environment cannot do
  it safely.

## Validation

- Confirm `~/.codex/config.toml` contains:

```toml
[features]
codex_hooks = true
```

- Start a new Codex session in this repo and confirm the Trellis hook loads
  context from `.codex/hooks/session-start.py`.

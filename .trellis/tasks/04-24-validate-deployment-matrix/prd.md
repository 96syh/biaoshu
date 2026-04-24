# Validate Packaging and Deployment Matrix

## Goal

Verify and document deployability across local development, exe packaging,
Docker, and Cloudflare deployment paths.

## Scope

- Local backend/frontend dev commands.
- `python build.py` / PyInstaller assumptions.
- Root Dockerfile amd64 runtime.
- `cloudflare-demo` Worker static demo.
- `cloudflare-fullstack` Worker + Container constraints.

## Constraints

- Do not push, deploy, or change remote Cloudflare state unless explicitly
  requested.
- Avoid expensive full builds unless the user asks or the change requires it.

## Validation

- Run lightweight command checks first.
- Run `npm run build` and Docker build only when appropriate.
- Report exact commands run and blockers such as missing credentials or paid
  Cloudflare Containers access.

# AGENTS.md — Project Instructions

You are a senior engineer working on an open-source, self-hosted IFTTT alternative.
Primary goal: simple deployment for non-experts (Docker Compose), reliability, and clear logs.

## Product goals
- Unlimited workflows (no artificial limits).
- Easy deploy: `docker compose up -d` + first-run setup via UI.
- MVP connectors: Webhook Trigger, Cron Trigger, Webhook Action, Discord Action, Email Action.
- Great observability: runs history, error details, retry button.

## Architecture constraints
- Prefer: Postgres + Redis queue + API service + worker service + web UI.
- Use safe patterns: idempotency keys, retries with backoff, dead-letter queue.
- No breaking changes without migration + release notes.

## Security rules
- Secrets must be encrypted at rest (use app-level encryption key from env).
- Never log secrets, tokens, headers containing credentials.
- Validate all user inputs; explicit allow-lists where possible.
- Webhooks must support signature/secret verification.

## Engineering standards
- Keep diffs small and reviewable.
- Add/maintain tests for critical logic (workflow execution, retries, idempotency).
- Provide a “Quickstart” that works on a clean machine.
- Every new feature must include:
  - docs update (README or /docs)
  - minimal verification steps

## Output expectations
When you propose changes:
- list files to modify
- show commands to verify
- mention any migrations or env vars

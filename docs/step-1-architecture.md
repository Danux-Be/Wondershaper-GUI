# Step 1 — Architecture Proposal and Initial Repository Structure

## Assumptions
- This repository is a fresh start with no existing application code.
- MVP scope for implementation phases is limited to:
  - Webhook Trigger
  - Webhook Action
  - Runs history/logging
- Stack choice: **Python + FastAPI** for simplicity and maintainability.

## Minimal Architecture (MVP)

### Services (Docker Compose)
1. **api** (FastAPI)
   - REST API for workflows, runs history, and webhook ingest endpoint.
   - Validates inputs and writes run/event metadata to Postgres.
   - Enqueues workflow execution jobs to Redis.

2. **worker** (Python worker process)
   - Consumes jobs from Redis queue.
   - Executes workflow steps (MVP: webhook action HTTP call).
   - Persists run status and step logs to Postgres.
   - Handles retries with bounded exponential backoff.

3. **postgres**
   - Source of truth for workflows, runs, run logs, and delivery attempts.

4. **redis**
   - Queue backend for decoupled execution.
   - Enables reliability under bursty webhook traffic.

### Execution flow (Webhook Trigger → Webhook Action)
1. External system sends HTTP request to `POST /v1/webhooks/{trigger_key}`.
2. API resolves trigger, creates a `run` record (`queued`), stores sanitized payload snapshot.
3. API enqueues job with idempotency key (`workflow_id + external_event_id/hash`).
4. Worker picks up job, marks run `running`, performs webhook action HTTP request.
5. Worker writes action result/logs and marks run `succeeded` or `failed`.
6. On failure, worker retries with backoff; after max retries marks dead-letter state in DB.

## Reliability and Security Baseline
- **Idempotency**: unique job key per trigger event to prevent duplicate runs.
- **Retries**: bounded exponential backoff for transient downstream errors.
- **Dead-letter tracking**: failed-after-retries runs remain queryable.
- **Input validation**: Pydantic schemas on all API inputs.
- **Secret handling**:
  - Action headers/secrets stored encrypted at rest (future step wiring).
  - Logs must redact authorization headers/tokens.
- **Safe logging**: structured logs with run/workflow IDs; no credential material.

## Initial Repository Structure

```text
.
├── docker-compose.yml                 # Step 2
├── .env.example                       # Step 2
├── README.md                          # Quickstart + verification (iterative)
├── docs/
│   ├── step-1-architecture.md         # This file
│   └── api-contracts.md               # Step 3
├── infra/
│   ├── postgres/
│   │   └── init.sql                   # Optional bootstrap SQL (Step 2/3)
│   └── redis/
│       └── redis.conf                 # Optional tuning (later)
├── services/
│   ├── api/
│   │   ├── Dockerfile                 # Step 2
│   │   ├── requirements.txt           # Step 2
│   │   ├── app/
│   │   │   ├── main.py                # FastAPI entrypoint
│   │   │   ├── config.py              # Env/config loader
│   │   │   ├── db.py                  # DB session/engine
│   │   │   ├── models.py              # SQLAlchemy models
│   │   │   ├── schemas.py             # Pydantic schemas
│   │   │   ├── routes/
│   │   │   │   ├── health.py          # /health
│   │   │   │   ├── webhooks.py        # Trigger ingest endpoint
│   │   │   │   ├── workflows.py       # MVP workflow CRUD
│   │   │   │   └── runs.py            # Runs history
│   │   │   └── services/
│   │   │       ├── queue.py           # Redis enqueue helpers
│   │   │       └── redaction.py       # Log redaction helpers
│   └── worker/
│       ├── Dockerfile                 # Step 2
│       ├── requirements.txt           # Step 2
│       └── worker/
│           ├── main.py                # Worker entrypoint
│           ├── jobs.py                # Queue consumer + handlers
│           ├── executor.py            # Webhook action execution
│           └── retry.py               # Backoff policy
├── shared/
│   └── py/
│       ├── __init__.py
│       ├── settings.py                # Shared env parsing (optional)
│       └── logging.py                 # Structured logger setup
└── tests/
    ├── integration/
    │   └── test_webhook_to_action.py  # Step 5 verification flow
    └── unit/
        └── test_retry_policy.py
```

## Verification for Step 1
- Validate the architecture proposal document exists and is readable.
- Validate repository currently contains only planning/docs artifacts.

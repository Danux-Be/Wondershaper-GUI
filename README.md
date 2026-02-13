# Danux

Self-hosted automation platform (IFTTT-like), focused on simple deployment and reliability.

## Step 2 status
This repository now includes base local infrastructure and service containers:
- API container (FastAPI skeleton)
- Worker container (placeholder process)
- PostgreSQL
- Redis

No workflow/business endpoints are implemented yet beyond healthcheck.

## Quickstart
1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
2. Start services:
   ```bash
   docker compose up -d --build
   ```
3. Check service status:
   ```bash
   docker compose ps
   ```
4. Verify API healthcheck:
   ```bash
   curl -fsS http://localhost:8000/health
   ```
5. View logs (optional):
   ```bash
   docker compose logs --tail=100 api worker postgres redis
   ```

## Environment variables
See `.env.example` for all variables required by compose.

## Security notes
- Replace `POSTGRES_PASSWORD` and `APP_ENCRYPTION_KEY` before non-local use.
- Do not commit `.env` with real secrets.

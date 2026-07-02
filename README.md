# EnterpriseGPT — Phase 1: Foundation

An Enterprise AI Knowledge Platform (RAG over your organization's documents), built phase by phase.

**Phase 1 delivers:** a clean-architecture FastAPI backend, PostgreSQL (pgvector-ready), Redis, and MinIO,
fully containerized, with liveness/readiness health checks and a passing test suite. No auth or RAG yet —
that's coming in later phases.

## Folder structure

```
enterprisegpt/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory + lifespan
│   │   ├── core/
│   │   │   ├── config.py           # Settings (env-driven)
│   │   │   ├── logging.py          # Structured logging setup
│   │   │   ├── exceptions.py       # Domain exception hierarchy
│   │   │   └── error_handlers.py   # Exception -> HTTP translation
│   │   ├── api/v1/
│   │   │   ├── router.py           # Aggregates all v1 routes
│   │   │   └── endpoints/health.py # /health/live, /health/ready
│   │   ├── infrastructure/
│   │   │   ├── database/session.py # Async SQLAlchemy engine/session
│   │   │   ├── cache/redis_client.py
│   │   │   └── storage/minio_client.py
│   │   ├── schemas/health.py       # Pydantic response models
│   │   ├── domain/                 # (empty — Phase 2+)
│   │   └── services/               # (empty — Phase 2+)
│   └── tests/
│       ├── conftest.py
│       └── test_health.py
└── docs/
```

## Prerequisites

- Docker + Docker Compose
- (Optional, for running tests outside Docker) Python 3.12

## How to run

1. **Set up environment variables:**
   ```bash
   cd enterprisegpt/backend
   cp .env.example .env
   ```
   The defaults in `.env.example` already match the Docker Compose service names
   (`postgres`, `redis`, `minio`), so no edits are needed to run via Docker.

2. **Start everything:**
   ```bash
   cd enterprisegpt
   docker compose up --build
   ```
   This starts PostgreSQL (with pgvector extension available), Redis, MinIO, and the FastAPI backend.

3. **Verify it's running:**
   - API docs (Swagger UI): http://localhost:8000/docs
   - Liveness probe: http://localhost:8000/api/v1/health/live → `{"status": "alive"}`
   - Readiness probe: http://localhost:8000/api/v1/health/ready → shows postgres/redis/minio status
   - MinIO console: http://localhost:9001 (login: `minioadmin` / `minioadmin`)

   **Expected output of `/api/v1/health/ready`:**
   ```json
   {
     "status": "ok",
     "version": "0.1.0",
     "environment": "local",
     "dependencies": [
       {"name": "postgres", "healthy": true},
       {"name": "redis", "healthy": true},
       {"name": "minio", "healthy": true}
     ]
   }
   ```

4. **Stop everything:**
   ```bash
   docker compose down          # stop containers
   docker compose down -v       # stop containers AND wipe data volumes
   ```

## How to run the backend locally without Docker (optional)

```bash
cd enterprisegpt/backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: change POSTGRES_HOST, REDIS_HOST, MINIO_ENDPOINT from
# service names (postgres/redis/minio) to localhost, since you're
# running the app on the host, not inside the Docker network.
uvicorn app.main:app --reload
```

You'll still need Postgres/Redis/MinIO running somewhere reachable (e.g. via
`docker compose up postgres redis minio` while running the backend natively).

## How to test

```bash
cd enterprisegpt/backend
pip install -r requirements.txt
pytest
```

**Expected output:** 3 tests pass (`test_liveness_returns_alive`,
`test_readiness_returns_dependency_statuses`, `test_openapi_docs_available`),
with a coverage report. These tests use an in-memory ASGI transport, so they
don't require Docker to be running — dependency health is asserted structurally,
not for actual connectivity.

## Git commit message

```
feat(phase-1): foundation — FastAPI backend, Postgres/pgvector, Redis, MinIO, health checks

- Clean architecture skeleton (core/api/infrastructure/services/schemas layers)
- Centralized env-driven config via pydantic-settings
- Structured logging + global exception handling
- Async SQLAlchemy engine, Redis client, MinIO client with health checks
- Liveness (/health/live) and readiness (/health/ready) endpoints
- Docker Compose stack: postgres(pgvector) + redis + minio + backend
- Pytest suite (3 tests, passing) using ASGI transport
```

## Phase 1 summary

- ✅ Clean, layered backend architecture (core / api / infrastructure / services / schemas)
- ✅ Environment-driven configuration, no hardcoded secrets
- ✅ Structured logging and centralized error handling
- ✅ PostgreSQL (pgvector image), Redis, MinIO wired up with health checks
- ✅ Kubernetes-style liveness/readiness probes
- ✅ Fully Dockerized, one-command startup
- ✅ Test suite passing (verified in this session — see below)

**Verified in this session:** dependencies installed, config bug fixed (CORS origin
list parsing), full pytest suite run and passing with 83% coverage.

## Next phase preview — Phase 2: Authentication & User Management

- Google OAuth login + JWT issuance/refresh
- User + Organization models (SQLAlchemy, Alembic migration)
- Role-Based Access Control (RBAC): Admin / Member / Viewer
- `/api/v1/auth/*` and `/api/v1/users/*` endpoints
- Protected route dependency (`get_current_user`)
- Tests for auth flows

Reply "approved" (or with changes you want) and I'll build Phase 2.

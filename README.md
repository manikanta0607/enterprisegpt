# EnterpriseGPT — Phase 2: Authentication & User Management

An Enterprise AI Knowledge Platform (RAG over your organization's documents), built phase by phase.

**Phase 1 delivered:** clean-architecture FastAPI backend, PostgreSQL (pgvector-ready), Redis, MinIO,
health checks, passing tests.

**Phase 2 adds:** Google OAuth login, JWT access/refresh tokens (with rotation + revocation),
User & Organization models with an Alembic migration, the repository pattern, and RBAC
(Viewer / Member / Admin) enforced on protected routes.

## What's new in Phase 2

```
backend/
├── alembic.ini
├── alembic/
│   ├── env.py                       # async migration environment
│   ├── script.py.mako
│   └── versions/0001_create_users_orgs.py
├── app/
│   ├── api/
│   │   ├── deps.py                  # get_current_user, repository DI
│   │   └── v1/endpoints/
│   │       ├── auth.py              # POST /auth/google, /auth/refresh, /auth/logout
│   │       └── users.py             # GET /users/me, GET /users (admin only)
│   ├── core/
│   │   ├── security.py              # JWT creation/verification
│   │   └── rbac.py                  # require_role() dependency
│   ├── domain/
│   │   ├── entities.py              # User, Organization (framework-agnostic)
│   │   └── enums.py                 # Role, role_at_least()
│   ├── infrastructure/database/models.py   # SQLAlchemy: User, Organization, RefreshToken
│   ├── repositories/                # UserRepository, OrganizationRepository
│   ├── schemas/{auth,user}.py       # Pydantic request/response models
│   └── services/
│       ├── google_auth.py           # Google ID token verification
│       └── auth_service.py          # login / refresh / logout orchestration
└── tests/
    ├── test_security.py             # JWT unit tests
    ├── test_rbac.py                 # role comparison unit tests
    └── test_users.py                # endpoint tests via dependency overrides
```

## How authentication works

1. Your frontend uses [Google Identity Services](https://developers.google.com/identity/gsi/web)
   to get an `id_token` for the signed-in user.
2. Frontend calls `POST /api/v1/auth/google` with that `id_token`.
3. Backend verifies the token's signature/audience with Google, then:
   - **New user:** creates an Organization + a User with role `ADMIN`.
   - **Returning user:** looks them up by their Google `sub`.
4. Backend returns an `access_token` (30 min default) and `refresh_token` (14 days default).
5. Frontend sends `Authorization: Bearer <access_token>` on subsequent requests.
6. When the access token expires, frontend calls `POST /api/v1/auth/refresh` with the refresh
   token to get a new pair (refresh tokens **rotate** — the old one is revoked on use).

## RBAC

Three roles, each including all permissions of the ones below it: `viewer` < `member` < `admin`.
Protect an endpoint with:
```python
current_user: User = Depends(require_role(Role.ADMIN))
```

## Prerequisites

- Docker + Docker Compose
- A Google OAuth Client ID (for real login) — see below. Not required to run tests or explore `/docs`.

## Setting up Google OAuth (for real login testing)

1. Go to https://console.cloud.google.com/apis/credentials
2. Create an **OAuth 2.0 Client ID** (type: Web application)
3. Add `http://localhost:3000` as an authorized JavaScript origin (frontend comes in Phase 3+)
4. Copy the Client ID into `backend/.env` as `GOOGLE_CLIENT_ID`

Without this, `/auth/google` will reject all tokens (expected) — everything else in Phase 2
(health checks, RBAC logic, JWT logic) works and is tested independently of Google.

## How to run

```bash
cd enterprisegpt/backend
cp .env.example .env
# Edit .env: set GOOGLE_CLIENT_ID and a real JWT_SECRET_KEY if testing login end-to-end

cd ..
docker compose up --build
```

Then **run the migration** (creates `organizations`, `users`, `refresh_tokens` tables):
```bash
docker compose exec backend alembic upgrade head
```

Check it worked:
- http://localhost:8000/docs — you'll now see `/auth/*` and `/users/*` endpoints
- http://localhost:8000/api/v1/health/ready — still `"status": "ok"`

## How to test

```bash
cd enterprisegpt/backend
pip install -r requirements.txt
pytest
```

**Expected output:** 13 tests passing (3 health + 3 RBAC + 3 JWT + 4 user-endpoint tests), ~77%
coverage. These tests use dependency overrides and don't require a live Postgres — full
DB-integration tests (real Alembic migration + real queries) are planned once CI has a
Postgres service container (Phase 8: CI/CD).

**Verified in this session:** dependencies installed, app boots with all 7 new routes registered
correctly, full pytest suite run and passing.

## Git commit message

```
feat(phase-2): auth & user management — Google OAuth, JWT, RBAC, Alembic migration

- Domain layer: User/Organization entities, Role enum with role_at_least()
- SQLAlchemy models: UserModel, OrganizationModel, RefreshTokenModel
- Repository pattern: UserRepository, OrganizationRepository
- JWT access/refresh tokens with rotation (app.core.security)
- Google ID token verification (app.services.google_auth)
- AuthService: login_with_google, refresh_access_token, logout
- RBAC: require_role() dependency, 403 error mapping
- Endpoints: POST /auth/google, /auth/refresh, /auth/logout, GET /users/me, GET /users
- Alembic async migration environment + initial migration (0001)
- 10 new tests (JWT, RBAC, protected endpoints via dependency overrides), all passing
```

## Phase 2 summary

- ✅ Google OAuth login with automatic org + admin-user provisioning for new accounts
- ✅ JWT access/refresh tokens, refresh token rotation, and revocation (logout)
- ✅ Repository pattern cleanly separating ORM models from domain entities
- ✅ RBAC with a reusable `require_role()` dependency, tested at all three role levels
- ✅ Async Alembic migration wired to the same settings as the app
- ✅ 13/13 tests passing (10 new + 3 carried over from Phase 1)

## Next phase preview — Phase 3: Document Ingestion

- Document upload endpoint (`POST /documents`) storing raw files in MinIO
- PDF, DOCX, PPTX parsing services
- OCR pipeline for scanned documents/images
- Chunking strategy (recursive character + semantic chunking options)
- Document + Chunk database models, linked to Organization
- Background processing via a task queue (so uploads don't block the request)
- Tests for each parser with sample fixture files

Reply "approved" (or with changes you want) and I'll build Phase 3.


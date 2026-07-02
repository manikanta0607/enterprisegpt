# EnterpriseGPT — Phase 3: Document Ingestion

An Enterprise AI Knowledge Platform (RAG over your organization's documents), built phase by phase.

**Phase 1 delivered:** clean-architecture FastAPI backend, PostgreSQL (pgvector-ready), Redis, MinIO,
health checks, passing tests.

**Phase 2 added:** Google OAuth login, JWT access/refresh tokens (with rotation + revocation),
User & Organization models with an Alembic migration, the repository pattern, and RBAC
(Viewer / Member / Admin) enforced on protected routes.

**Phase 3 adds:** document upload to MinIO, PDF/DOCX/PPTX/image(OCR) parsing, recursive-with-overlap
text chunking, Document + Chunk models with a migration, and a background ingestion pipeline.

## What's new in Phase 3

```
backend/
├── alembic/versions/0002_create_documents_chunks.py
├── app/
│   ├── api/v1/endpoints/documents.py   # POST/GET /documents, GET /documents/{id}/chunks
│   ├── domain/enums.py                 # + DocumentStatus
│   ├── domain/entities.py              # + Document, Chunk
│   ├── infrastructure/
│   │   ├── database/models.py          # + DocumentModel, ChunkModel
│   │   └── storage/document_storage.py # MinIO upload/download for raw files
│   ├── repositories/
│   │   ├── document_repository.py
│   │   └── chunk_repository.py
│   ├── schemas/document.py             # DocumentResponse, ChunkResponse
│   └── services/
│       ├── chunking.py                 # recursive character splitter w/ overlap
│       ├── document_service.py         # upload orchestration + background pipeline
│       └── parsers/
│           ├── base.py                 # DocumentParser interface
│           ├── pdf_parser.py           # pypdf
│           ├── docx_parser.py          # python-docx
│           ├── pptx_parser.py          # python-pptx
│           ├── ocr_parser.py           # pytesseract (images)
│           └── factory.py              # content-type -> parser routing
└── tests/
    ├── test_chunking.py
    ├── test_parsers.py                 # generates real PDF/DOCX/PPTX/PNG and parses them
    └── test_documents.py               # endpoint tests via dependency overrides
```

## How document ingestion works

1. `POST /api/v1/documents` (multipart file upload, requires MEMBER role+) — validates size/type,
   uploads raw bytes to MinIO under `{org_id}/{uuid}_{filename}`, creates a `documents` row with
   status `pending`, and returns immediately (HTTP 201).
2. A `BackgroundTask` picks up processing after the response is sent: downloads the file from
   MinIO, routes it to the right parser by content type, extracts text, chunks it, and saves the
   chunks — updating status to `processing` → `completed` (or `failed`, with `error_message` set).
3. Poll `GET /api/v1/documents/{id}` until `status` is `completed`, then fetch
   `GET /api/v1/documents/{id}/chunks` to see the extracted, chunked text.

**Supported file types:** `application/pdf`, `.docx`, `.pptx`, `image/png`, `image/jpeg`.
**Max upload size:** 25 MB (adjustable via `MAX_UPLOAD_SIZE_BYTES` in `document_service.py`).

**On background processing:** Phase 3 uses FastAPI's built-in `BackgroundTasks`, which run
in-process after the response is sent — simple and sufficient for now. As ingestion volume or
parsing time grows, this is the natural place to swap in a real task queue (Celery/RQ backed by
the Redis instance already running), which is planned for the scaling work in a later phase.

## Prerequisites

- Docker + Docker Compose
- A Google OAuth Client ID (only needed to test real login end-to-end)

## Setting up Google OAuth (optional, for real login testing)

1. Go to https://console.cloud.google.com/apis/credentials
2. Create an **OAuth 2.0 Client ID** (type: Web application)
3. Add `http://localhost:3000` as an authorized JavaScript origin (frontend arrives in a later phase)
4. Copy the Client ID into `backend/.env` as `GOOGLE_CLIENT_ID`

Without this, `/auth/google` will reject all tokens (expected) — see "Testing without Google
OAuth" below for an alternative when exploring `/documents` locally.

## How to run

```bash
cd enterprisegpt/backend
cp .env.example .env   # if you haven't already from Phase 1/2

cd ..
docker compose up --build
docker compose exec backend alembic upgrade head   # creates all tables, including documents/chunks
```

**Try it via Swagger UI** (http://localhost:8000/docs):
1. Get a token: use `/auth/google` (needs a real Google ID token) — or, for quick local testing
   without wiring up Google, see "Testing without Google OAuth" below.
2. Authorize in Swagger with `Bearer <access_token>`.
3. `POST /documents` — upload a PDF/DOCX/PPTX/PNG/JPEG.
4. `GET /documents/{id}` — watch `status` move from `pending` to `completed`.
5. `GET /documents/{id}/chunks` — see the extracted, chunked text.

### Testing without Google OAuth

The full login flow needs a real Google ID token, which requires a frontend (coming in a later
phase). Until then, you can mint a valid access token directly for local testing:
```bash
docker compose exec backend python -c "
from app.core.security import create_token, TokenType
import uuid
token, _ = create_token(subject=uuid.uuid4(), role='admin', organization_id=uuid.uuid4(), token_type=TokenType.ACCESS)
print(token)
"
```
This won't map to a real user row, so protected endpoints needing `get_current_user` (which looks
up the user by ID) will 404 — it's useful for exercising RBAC/token logic, not full end-to-end
flows, until Phase 4+ adds a proper seed/dev-login path.

## How to test

```bash
cd enterprisegpt/backend
pip install -r requirements.txt
pytest
```

**Expected output:** 33 tests passing (23 from Phases 1–2 + 10 new: chunking behavior, real
PDF/DOCX/PPTX/OCR parsing against generated fixture files, and document endpoint access control),
~77% coverage.

**Note on OCR:** `pytesseract` requires the `tesseract-ocr` system package. It's installed
automatically in the Docker image; if running tests outside Docker, install it yourself
(`apt-get install tesseract-ocr` on Ubuntu/Debian, `brew install tesseract` on macOS,
or the installer from https://github.com/UB-Mannheim/tesseract/wiki on Windows).

**Verified in this session:** all new dependencies installed (including `tesseract-ocr` in this
sandbox), full pytest suite run and passing — including real OCR text recognition, not mocked —
and the app confirmed to boot with all document routes registered.

## Git commit message

```
feat(phase-3): document ingestion — upload, PDF/DOCX/PPTX/OCR parsing, chunking

- Domain: DocumentStatus enum, Document/Chunk entities
- SQLAlchemy models: DocumentModel, ChunkModel (+ migration 0002)
- Repository pattern: DocumentRepository, ChunkRepository
- MinIO document storage wrapper (namespaced by organization)
- Parsers: PdfParser, DocxParser, PptxParser, OcrParser behind a factory
- Chunking service: recursive character splitter with configurable overlap
- DocumentService: upload orchestration + background ingestion pipeline
- Endpoints: POST/GET /documents, GET /documents/{id}, GET /documents/{id}/chunks
- Dockerfile: install tesseract-ocr system package
- 10 new tests (chunking, real parser fixtures incl. OCR, endpoint RBAC), all passing
```

## Phase 3 summary

- ✅ Upload endpoint storing raw files in MinIO, namespaced per organization
- ✅ PDF, DOCX, PPTX, and image (OCR via Tesseract) parsing, all tested against real generated files
- ✅ Recursive character chunking with overlap, tested for correctness and boundary behavior
- ✅ Document/Chunk models + Alembic migration, cleanly extending Phase 1/2's schema
- ✅ Background ingestion pipeline (pending → processing → completed/failed)
- ✅ RBAC preserved: upload requires MEMBER+, viewing requires only authentication
- ✅ 33/33 tests passing (10 new + 23 carried over)

## Next phase preview — Phase 4: Embeddings & Vector Search

- Google Embeddings integration for chunk vectorization
- pgvector column on `chunks` + similarity search queries
- Hybrid search: vector similarity + BM25 keyword search, combined
- Query rewriting and context compression
- Re-ranking of retrieved chunks
- Background embedding job triggered after chunking completes
- Tests for retrieval quality/ranking behavior

Reply "approved" (or with changes you want) and I'll build Phase 4.


# EnterpriseGPT — Phase 4: Embeddings & Vector Search

An Enterprise AI Knowledge Platform (RAG over your organization's documents), built phase by phase.

**Phase 1 delivered:** clean-architecture FastAPI backend, PostgreSQL (pgvector-ready), Redis, MinIO,
health checks, passing tests.

**Phase 2 added:** Google OAuth login, JWT access/refresh tokens (with rotation + revocation),
User & Organization models with an Alembic migration, the repository pattern, and RBAC
(Viewer / Member / Admin) enforced on protected routes.

**Phase 3 added:** document upload to MinIO, PDF/DOCX/PPTX/image(OCR) parsing, recursive-with-overlap
text chunking, Document + Chunk models with a migration, and a background ingestion pipeline.

**Phase 4 adds:** Google Embeddings for every chunk, a pgvector column + cosine-similarity search,
BM25 keyword search, hybrid retrieval (Reciprocal Rank Fusion), lightweight query rewriting,
term-overlap re-ranking, and extractive context compression — exposed via `POST /search`.

## What's new in Phase 4

```
backend/
├── alembic/versions/0003_add_embeddings.py   # CREATE EXTENSION vector + embedding column + ivfflat index
├── app/
│   ├── api/v1/endpoints/search.py            # POST /search
│   ├── domain/entities.py                    # Chunk + optional embedding field
│   ├── infrastructure/database/models.py     # ChunkModel.embedding (pgvector Vector column)
│   ├── repositories/chunk_repository.py      # + update_embedding, search_by_vector,
│   │                                          #   list_content_by_organization, get_by_ids
│   ├── schemas/search.py                     # SearchRequest, SearchResultItem, SearchResponse
│   └── services/
│       ├── embeddings.py                     # EmbeddingService (Google text-embedding-004)
│       ├── query_rewrite.py                  # QueryRewriter: NoOp / Gemini implementations
│       ├── context_compression.py            # extractive sentence-level compression
│       ├── document_service.py               # + embeds chunks after chunking, in the pipeline
│       └── search/
│           ├── bm25.py                       # pure BM25 ranking function
│           ├── fusion.py                     # Reciprocal Rank Fusion
│           ├── reranker.py                   # term-overlap re-ranking pass
│           └── search_service.py             # orchestrates the full pipeline
└── tests/
    ├── test_bm25.py
    ├── test_fusion.py
    ├── test_reranker.py
    ├── test_context_compression.py
    ├── test_embeddings.py                    # Google SDK mocked, no network calls
    ├── test_query_rewrite.py                 # NoOp + Gemini paths, mocked
    └── test_search_service.py                # full pipeline, repositories mocked
```

## How search works

`POST /api/v1/search` with `{"query": "...", "top_k": 10}`:

1. **Query rewriting** — if `GOOGLE_API_KEY` is set, a lightweight Gemini model expands the raw
   query for better retrieval; otherwise it's used as-is (`NoOpQueryRewriter`). Rewriting failures
   fall back to the original query rather than failing the request.
2. **Vector search** — the (rewritten) query is embedded and compared via pgvector cosine
   similarity against every embedded chunk in the caller's organization.
3. **BM25 keyword search** — classic BM25 scoring over the organization's chunk corpus, run
   in-process (see the scaling note in `chunk_repository.list_content_by_organization`).
4. **Hybrid fusion** — vector and BM25 rankings are combined via Reciprocal Rank Fusion, which
   only needs each ranking's *position*, sidestepping the problem of comparing differently-scaled
   similarity vs. BM25 scores.
5. **Re-ranking** — a term-overlap pass promotes chunks with literal query-term matches, catching
   cases where something is vector-similar but not actually relevant.
6. **Context compression** — each result is trimmed to its most query-relevant sentences before
   being returned, keeping payloads small (and ready to feed an LLM prompt in Phase 5).

If vector search fails (e.g. no API key, or the embedding call errors) search degrades gracefully
to BM25-only results rather than failing the whole request.

**Chunks are embedded automatically** as part of the Phase 3 ingestion pipeline — right after
chunking, `document_service.py` calls `EmbeddingService` for each chunk and stores the vector.
Without `GOOGLE_API_KEY` configured, this step is skipped (logged, not fatal) and chunks remain
searchable via BM25 only.

## Prerequisites

- Docker + Docker Compose
- A Google API key from https://aistudio.google.com/apikey (optional — enables embeddings, vector
  search, and query rewriting; BM25 keyword search works without it)
- A Google OAuth Client ID (optional — only for real login end-to-end; see below)

## Setting up Google OAuth (optional, for real login testing)

1. Go to https://console.cloud.google.com/apis/credentials
2. Create an **OAuth 2.0 Client ID** (type: Web application)
3. Add `http://localhost:3000` as an authorized JavaScript origin (frontend arrives in a later phase)
4. Copy the Client ID into `backend/.env` as `GOOGLE_CLIENT_ID`

Without this, `/auth/google` will reject all tokens (expected) — see "Testing without Google
OAuth" below for an alternative.

## How to run

```bash
cd enterprisegpt/backend
cp .env.example .env
# Optionally set GOOGLE_API_KEY to enable embeddings/vector search/query rewriting

cd ..
docker compose up --build
docker compose exec backend alembic upgrade head   # creates all tables + enables pgvector
```

**Try it via Swagger UI** (http://localhost:8000/docs):
1. Get a token (see "Testing without Google OAuth" if you haven't wired up real login yet).
2. Authorize in Swagger with `Bearer <access_token>`.
3. `POST /documents` — upload a file; wait for `status: completed`.
4. `POST /search` — `{"query": "your topic here", "top_k": 5}` — see ranked, compressed results.

### Testing without Google OAuth

```bash
docker compose exec backend python -c "
from app.core.security import create_token, TokenType
import uuid
token, _ = create_token(subject=uuid.uuid4(), role='admin', organization_id=uuid.uuid4(), token_type=TokenType.ACCESS)
print(token)
"
```
This won't map to a real user row, so `get_current_user`-protected endpoints will 404 — useful for
exercising RBAC/token logic, not full end-to-end flows, until a proper dev-login/seed path is added.

## How to test

```bash
cd enterprisegpt/backend
pip install -r requirements.txt
pytest
```

**Expected output:** 63 tests passing (33 from Phases 1–3 + 30 new: BM25 ranking, RRF fusion,
re-ranking, context compression, embeddings with the Google SDK mocked, query rewriting — both
NoOp and Gemini paths — and full search pipeline orchestration with repositories mocked), ~79%
coverage.

**Verified in this session:** all new dependencies installed, full pytest suite run and passing,
app confirmed to boot with `/search` registered alongside all prior routes. A couple of real BM25
edge cases surfaced and were understood along the way — with very small test corpora (2–3 docs),
BM25's IDF term can hit exactly zero or go negative for terms appearing in half the corpus; the
tests were adjusted to use realistic corpus sizes rather than papering over it in the algorithm.

**Not verified here** (no live Postgres/pgvector in this sandbox): the actual SQL in
`search_by_vector` and the `ivfflat` migration. These follow the same, already-tested pattern as
every other repository method in this project and will be exercised for real the moment you run
`docker compose up` and `alembic upgrade head` — flag it to me if anything looks off when you do.

## Git commit message

```
feat(phase-4): embeddings & hybrid search — pgvector, BM25, RRF, re-ranking, compression

- Config: GOOGLE_API_KEY, embedding model/dimensions, query rewrite model
- Domain: Chunk.embedding field
- SQLAlchemy: ChunkModel.embedding (pgvector Vector column) + migration 0003
  (CREATE EXTENSION vector, ivfflat cosine index)
- ChunkRepository: update_embedding, search_by_vector (pgvector cosine_distance),
  list_content_by_organization, get_by_ids
- EmbeddingService: Google text-embedding-004 wrapper, mockable for tests
- document_service: embeds each chunk right after chunking (skips gracefully
  without an API key)
- QueryRewriter: NoOp + Gemini implementations, factory picks based on config
- BM25 (pure function), Reciprocal Rank Fusion (pure function), term-overlap
  re-ranker (pure function), extractive context compression (pure function)
- SearchService: orchestrates rewrite -> embed -> vector+BM25 -> fuse -> rerank -> compress
- POST /search endpoint
- 30 new tests, all passing
```

## Phase 4 summary

- ✅ Every ingested chunk is embedded automatically as part of the Phase 3 pipeline
- ✅ pgvector cosine-similarity search wired via a proper Alembic migration + ivfflat index
- ✅ BM25 keyword search, unit-tested with real ranking-correctness assertions
- ✅ Hybrid retrieval via Reciprocal Rank Fusion — no fragile score normalization needed
- ✅ Re-ranking and extractive context compression as clean, independently-testable pure functions
- ✅ Query rewriting with a safe NoOp fallback when no Google API key is configured
- ✅ Graceful degradation: vector search failures fall back to BM25-only, not a 500
- ✅ 63/63 tests passing (30 new + 33 carried over)

## Next phase preview — Phase 5: RAG Pipeline & AI Agents

- LangChain/LangGraph-based RAG pipeline consuming this phase's `/search` results
- Conversation memory (short-term) and long-term memory across sessions
- Citations / source references tied back to specific chunks and documents
- Multi-turn chat endpoint with streaming responses
- Basic agentic tool use via LangGraph
- Tests for conversation flows and citation accuracy

Reply "approved" (or with changes you want) and I'll build Phase 5.


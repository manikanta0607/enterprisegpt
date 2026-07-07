# EnterpriseGPT — Phase 5: RAG Pipeline & AI Agents

An Enterprise AI Knowledge Platform (RAG over your organization's documents), built phase by phase.

**Phase 1 delivered:** clean-architecture FastAPI backend, PostgreSQL (pgvector-ready), Redis, MinIO,
health checks, passing tests.

**Phase 2 added:** Google OAuth login, JWT access/refresh tokens (with rotation + revocation),
User & Organization models with an Alembic migration, the repository pattern, and RBAC
(Viewer / Member / Admin) enforced on protected routes.

**Phase 3 added:** document upload to MinIO, PDF/DOCX/PPTX/image(OCR) parsing, recursive-with-overlap
text chunking, Document + Chunk models with a migration, and a background ingestion pipeline.

**Phase 4 added:** Google Embeddings for every chunk, a pgvector column + cosine-similarity search,
BM25 keyword search, hybrid retrieval (Reciprocal Rank Fusion), lightweight query rewriting,
term-overlap re-ranking, and extractive context compression — exposed via `POST /search`.

**Phase 5 adds:** a LangGraph RAG pipeline (retrieve → generate) built on top of Phase 4's search,
multi-turn conversations with short-term + summarized long-term memory, citations/source references
on every assistant reply, and both a synchronous and a streaming chat endpoint.

## What's new in Phase 5

```
backend/
├── alembic/versions/0004_create_conversations_messages.py
├── app/
│   ├── api/v1/endpoints/conversations.py     # POST/GET /conversations, GET .../messages,
│   │                                          #   POST .../messages, POST .../messages/stream
│   ├── domain/entities.py                    # Citation, Conversation, Message
│   ├── domain/enums.py                       # + MessageRole
│   ├── infrastructure/database/models.py     # ConversationModel, MessageModel (citations as JSON)
│   ├── repositories/
│   │   ├── conversation_repository.py
│   │   └── message_repository.py
│   ├── schemas/conversation.py                # ConversationResponse, MessageResponse, etc.
│   └── services/
│       ├── conversation_service.py            # orchestrates a full chat turn end-to-end
│       └── rag/
│           ├── graph.py                       # LangGraph: retrieve -> generate
│           ├── generation.py                  # GenerationService (Gemini, sync + streaming)
│           └── memory.py                      # short-term history + long-term summarization
└── tests/
    ├── test_memory.py
    ├── test_rag_graph.py                      # graph + prompt assembly, search/generation mocked
    └── test_conversation_service.py           # full orchestration, repositories/services mocked
```

## How the RAG pipeline works

`POST /api/v1/conversations` creates a thread; `POST /api/v1/conversations/{id}/messages` sends a
turn and returns the assistant's reply:

1. The user's message is persisted immediately.
2. **Memory is assembled**: the conversation's stored summary (if any) plus its most recent
   `MAX_HISTORY_MESSAGES` turns, verbatim.
3. A **LangGraph** graph with two nodes runs: `retrieve` (calls Phase 4's `SearchService` — full
   hybrid search: vector + BM25 + fusion + re-rank + compression) → `generate` (calls Gemini with
   the retrieved context + memory + question).
4. The retrieved chunks become **citations** on the assistant's reply — each one's chunk ID,
   document ID, filename, and excerpt, so answers are traceable back to source documents.
5. The assistant reply is persisted. If the conversation has grown past
   `SUMMARIZE_AFTER_MESSAGES` turns, older history is compressed into a running summary (an LLM
   call) and stored on the conversation — this is the **long-term memory** mechanism, keeping
   context available indefinitely without the prompt growing unbounded.

`POST /api/v1/conversations/{id}/messages/stream` runs the same retrieval + memory + persistence
steps, but streams the generated answer back as plain-text chunks as Gemini produces them, rather
than waiting for the full response. The complete message (with citations) is persisted once the
stream finishes — fetch `GET .../messages` afterward to see them.

**Why LangGraph for just two nodes:** the graph structure (rather than a plain function call) is
what makes this extensible — a later phase can add a router node (e.g. "does this need document
search at all, or is it a general question?"), additional tools, or parallel retrieval branches,
without restructuring the core flow. Each node is independently testable (see `test_rag_graph.py`).

**Known simplification:** the streaming endpoint iterates over the Gemini SDK's synchronous
streaming generator directly inside an async endpoint, which blocks the event loop for the
duration of each chunk's network wait. Fine for demonstrating the feature and for
moderate/single-worker load; running that iteration in a thread pool (`asyncio.to_thread`) is the
straightforward next step if this needs to scale to many concurrent streaming requests.

## Prerequisites

- Docker + Docker Compose
- A Google API key from https://aistudio.google.com/apikey (needed for embeddings, vector search,
  query rewriting, **and now chat generation and summarization**; without it, `/conversations`
  endpoints will fail at the generation step even though retrieval still works via BM25)
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
# Set GOOGLE_API_KEY to actually get chat replies — required for Phase 5's /conversations
# endpoints to produce real answers (retrieval works without it, generation does not)

cd ..
docker compose up --build
docker compose exec backend alembic upgrade head   # creates all tables, incl. conversations/messages
```

**Try it via Swagger UI** (http://localhost:8000/docs):
1. Get a token (see "Testing without Google OAuth" if you haven't wired up real login yet).
2. Authorize in Swagger with `Bearer <access_token>`.
3. `POST /documents` — upload a file; wait for `status: completed`.
4. `POST /conversations` — note the returned `id`.
5. `POST /conversations/{id}/messages` — `{"content": "your question about the document"}` — get
   a grounded answer with citations.
6. `POST /conversations/{id}/messages/stream` — same idea, but streamed (Swagger UI will show the
   raw streamed body; a real client would read it incrementally).

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

**Expected output:** 80 tests passing (63 from Phases 1–4 + 17 new: memory assembly and
summarization triggers, the LangGraph pipeline with search/generation mocked, and full
conversation-service orchestration — including the not-found/tenant-isolation and
summarization-threshold paths — with repositories and services mocked), ~78% coverage.

**Verified in this session:** all new dependencies installed (`langgraph`, `langchain-core`), full
pytest suite run and passing, app confirmed to boot with all 5 new conversation routes registered
alongside every prior route (21 routes total).

**Not verified here** (no live Postgres/pgvector or real Gemini API access in this sandbox): the
actual SQL behind the new repositories, the `alembic upgrade head` run for migration 0004, and a
real end-to-end generation call. These follow the same tested-pattern-but-DB-unverified situation
as prior phases — flag it to me if anything looks off once you run it against real infrastructure.

## Git commit message

```
feat(phase-5): RAG pipeline & AI agents — LangGraph, conversations, memory, citations, streaming

- Domain: MessageRole enum, Citation/Conversation/Message entities
- SQLAlchemy: ConversationModel, MessageModel (citations as JSON) + migration 0004
- Repository pattern: ConversationRepository, MessageRepository
- GenerationService: Gemini wrapper for sync + streaming answer generation
- rag/memory.py: short-term history assembly + long-term summarization triggers
- rag/graph.py: LangGraph retrieve -> generate pipeline, citation mapping
- ConversationService: orchestrates a full chat turn (persist, retrieve,
  generate, persist reply, maybe-summarize) plus a streaming variant
- Endpoints: POST/GET /conversations, GET .../messages, POST .../messages,
  POST .../messages/stream
- 17 new tests (memory logic, graph orchestration, conversation service,
  all with search/generation/repositories mocked), all passing
```

## Phase 5 summary

- ✅ LangGraph-based RAG pipeline (retrieve → generate), extensible by design
- ✅ Multi-turn conversations with persisted history
- ✅ Short-term memory (recent turns) + long-term memory (auto-summarization past a threshold)
- ✅ Citations/source references on every assistant reply, traceable to specific chunks/documents
- ✅ Both synchronous and streaming chat endpoints
- ✅ Tenant isolation enforced on every conversation/message operation, tested explicitly
- ✅ 80/80 tests passing (17 new + 63 carried over)

## Next phase preview — Phase 6: Admin Dashboard & Observability

- Admin dashboard endpoints: org-wide document/user/conversation stats
- Cost tracking and LLM usage analytics (tokens in/out per request, per org)
- Feedback system (thumbs up/down on assistant replies)
- Prompt versioning
- LangSmith, Prometheus, and OpenTelemetry integration
- Evaluation pipeline + basic hallucination detection

Reply "approved" (or with changes you want) and I'll build Phase 6.


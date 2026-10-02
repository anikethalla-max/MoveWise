# Progress

## Phase 1

Implemented the FastAPI workspace API, SQLAlchemy models, Alembic migration, profile and housing CRUD, exact Decimal budget totals, synthetic Bengaluru seed script, and responsive Next.js interface. The local session cookie scopes all record access. Added backend tests and a Playwright browser journey.

Verification performed on 2026-10-02:

- `npm run build`: passed with Next.js 16.3.8.
- `npm run typecheck`: passed.
- `npm install`: audit reported zero vulnerabilities after updating Next.js.
- `python -m alembic upgrade head --sql`: passed and generated PostgreSQL DDL.
- `python -m alembic upgrade head` with an in-memory SQLite URL: passed.
- The three backend test functions passed when run directly. `pytest -q` printed three passes but did not terminate in this environment; its exit status is unverified.

Phase 1 implementation is complete. The user will check the full running application after all development phases. A live PostgreSQL migration and persistence run and the Playwright browser journey are deferred until that review; they have not been verified. Docker is optional: any reachable PostgreSQL 17 server with pgvector and the configured database can be used. The pytest runner printed all three passing tests but did not exit cleanly in this environment; direct invocation of the three test functions exited successfully. These limits remain open verification items for final delivery.

## Phase 2

Implemented private PDF/TXT/Markdown upload and management, page and section aware chunking, pgvector storage and semantic retrieval, persisted ingestion jobs with retry and stale-job recovery, and a bounded Document Agent with list/search/excerpt tools and validated citations. Added a document page with status, selected-document scope, question answers, citations, conflict and missing-information displays, and observable tool activity. Added an optional synthetic shared guide, separate from private workspace documents.

Verification performed on 2026-10-02:

- `npm run build` and `npm run typecheck`: passed.
- Alembic upgrade to head against isolated in-memory SQLite: passed; PostgreSQL SQL generation: passed.
- Eight deterministic backend test functions passed by direct invocation, including ingestion, duplicate-safe retry, private file deletion, semantic retrieval, workspace isolation, unsupported and conflicting answer structures, citation rejection, upload validation, visible AI errors, and scanned-PDF OCR messaging. Pytest printed eight passes but did not exit cleanly in this environment; its exit status remains unverified.

Live PostgreSQL/pgvector and OpenAI provider calls were not run: no PostgreSQL server or API key is available in this environment. The user will review the running application after all phases. These remain explicit final verification items, and mock provider output has not been presented as a real AI run.

## Phase 3

Implemented Housing and Planning specialists on the shared bounded tool runtime. Housing tools read the scoped profile and saved homes, calculate exact budget totals, and compare homes with documented rule weights and visible unknowns. Users can ask the Housing Agent for recommendations and select a saved home. The Planning Agent reads the profile, current plan, selected home, deterministic budget, and document evidence before creating a pending proposal. Plans have immutable versions, task progress, exact change previews, confirmation and cancellation, citation validation, stale context checks, and idempotent confirmation. The UI provides housing explanations, plan checklists, progress, version history, and observed specialist tool activity.

Verification performed on 2026-10-02:

- `npm run build`: passed, including Housing advisor and Moving plan routes.
- `npm run typecheck`: passed.
- `python -m alembic upgrade head` against isolated in-memory SQLite: passed; PostgreSQL SQL generation: passed.
- Fourteen backend test functions passed by direct invocation. They cover prior features plus housing arithmetic/scoring and tool use, plan dates, proposal preview, cancel, stale version and context, duplicate confirmation, workspace ownership, completed-task preservation, and document citation validation. `pytest -q` printed 14 passes but did not exit cleanly in this environment; its exit status is unverified.

No live OpenAI run was performed because `OPENAI_API_KEY` is absent. No PostgreSQL server is reachable locally, so live PostgreSQL persistence, pgvector retrieval, and browser journeys remain deferred to the user's full-app review. Mock-provider results are identified as tests and are not represented as real agent runs.

## Phase 4

Implemented the Relocation Coordinator with selective Housing, Document, and Planning delegation through structured tools. Existing specialists retain their own instructions and tools, and cannot delegate recursively. Coordinator runs keep specialist child IDs, structured results, citations, missing information, and partial failures. A shared runtime budget enforces tool steps, elapsed time, and an estimated token cap; provider calls receive remaining-time bounds and transient LLM requests retry once. Cancellation stops later calls and delegations. Conversations, messages, runs, and structured tool events are persisted per workspace. The unified Assistant shows saved history, SSE activity, specialist statuses, citations, housing comparisons, and plan proposal confirmation controls. Message submission is idempotent by workspace-scoped request key; SSE reconnects only read saved events.

Verification performed on 2026-10-02:

- `npm run build`: passed, including the `/assistant` route.
- `npm run typecheck`: passed.
- Alembic upgrade to head against isolated in-memory SQLite and PostgreSQL SQL generation: passed.
- Twenty-two backend test functions passed by direct invocation. Phase 4 cases cover selective routing, combined delegation, citation preservation, partial failure, shared limits, cancellation, durable run history, idempotent submission, SSE, and workspace isolation. `pytest -q` printed 22 passes but did not exit cleanly in this environment; its exit status is unverified.

No integrated real-provider run was possible: `OPENAI_API_KEY` is absent and no PostgreSQL server is reachable on localhost. The user plans a full-app review after development. In-process background runs also need operational recovery if the server stops mid-run; this remains for Phase 5 readiness work. No mock output has been represented as a real AI run.

## Phase 5 — final delivery

Completed the full synthetic journey with profile, three clearly labeled homes, budget, private agreement upload, cited Document answer, Housing comparison, Planning proposal, Coordinator request, explicit confirmation, refresh, and screenshots. Improved text encoding and visible simulation labeling. Added established OIDC identity mapping for production, HTTPS/CORS and private-storage production guards, per-workspace request and upload limits, 10 MB file and 100 MB workspace quotas, database readiness, durable assistant worker recovery without mutation replay, container templates, and token usage/cost fields when provider usage and configured prices exist. The browser demonstration uses a disposable SQLite database and scripted providers only. The production template is not deployed.

Created versioned evaluation dataset v1 and deterministic harness. Measured four of four evidence retrieval hits, five of five scripted RAG answer cases, one of five evidence-blind baseline answers, valid citations in five of five cases, support in four of four cited cases, three of three Coordinator routes, one of three fixed single-specialist tasks, three of three multi-agent tasks, and zero budget violations in the fixture. Median local RAG latency was 2.37 ms versus 0.24 ms without retrieval. The raw run is in `docs/evaluation-results/mock-v1.json`; `docs/evaluation.md` explains scoring and the narrow limits. Provider token usage and estimated cost were unavailable. The first combined browser attempt hit the old cumulative token estimate cap; raising it to 40,000 allowed the full bounded run. These measurements are mock plumbing results, not real model quality claims.

Verification performed on 2026-10-02:

- `python -m pytest -q`: **26 passed in 2.31s**, exit 0, including Phase 5 auth guard, identity mapping, rate/quota, and interrupted-run recovery tests.
- `npm run test:e2e`: **1 passed**, exit 0, covering the complete synthetic scripted browser journey and screenshots.
- `npm run build`: passed, with all application routes generated; `npm run typecheck`: passed.
- Alembic upgrade to head against isolated SQLite: passed. PostgreSQL SQL generation passed earlier; no live PostgreSQL/pgvector migration or query was run.
- Deterministic evaluation harness: completed and wrote the versioned JSON results.

MoveWise development for the five requested phases is complete. A real provider run, live PostgreSQL/pgvector check, external OIDC login, reverse proxy/TLS, backups, and production deployment were not verified because this environment has no provider credential, PostgreSQL service, or configured identity provider. The user plans to review the running application after development. Scanned PDF OCR, live property data, and production multi-replica shared rate limiting are outside the delivered behavior. Do not present scripted screenshots or scores as real AI results.

## Local Ollama follow-up

Added backend-only Ollama chat and embedding adapters with configurable loopback URL and model names. The chat adapter translates Ollama tool calls and tool results to the shared bounded runtime contract and records Ollama token usage when returned. The embedding adapter accepts a model's native vector length; migration `0006` changes PostgreSQL storage to dimensionless `vector`. Local setup is documented in the README. Existing documents must be reingested after changing embedding models, including when dimensions match. Public production remains guarded against mock or unreviewed local-provider configuration.

Verification: `python -m pytest -q` passed **28 tests**; SQLite migration to head and PostgreSQL SQL generation passed. Adapter tests mocked Ollama HTTP and covered tool round trips, response normalization, usage fields, and native-size embeddings. **No real Ollama model call was performed:** `ollama --version` returned 0.35.0, but both `ollama list` and the local `/api/tags` endpoint returned an empty model list. The actual chat model name, tool-calling behavior, and embedding model remain unverified until a model is available in this Ollama instance.

## LangChain and LangGraph follow-up

Replaced the shared hand-written model/tool loop with a LangGraph `StateGraph` using conditional model/tool transitions. LangChain `StructuredTool` now wraps each allowed tool with its declared argument schema while preserving server-bound workspace ownership, shared limits, event records, provider retries, specialist delegation, citation checks, and separate plan confirmation. Pinned `langchain==1.4.3` and `langgraph==1.2.11`. This is actual runtime use, so the README resume draft now names both technologies.

Verification: `python -m pytest -q` passed **28 tests**; the scripted full Playwright journey passed **1 test** after narrowing an ambiguous final heading assertion. The versioned dataset was rerun through the new runtime at `docs/evaluation-results/mock-v1-langgraph.json`: correctness, routing, and task outcomes matched the previous mock run, while median local RAG/no-retrieval latency increased from 2.37/0.24 ms to 9.54/5.32 ms. No real Ollama model was available for an integrated run, and PostgreSQL pgvector is still absent from the user's local PostgreSQL installation.

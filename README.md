# Veriora 2.0

Veriora is an evidence-focused legal document workspace. It explains captured text and links interpretations to checkable source passages. It does not prove actual conduct, enforceability or court admissibility.

## Features and status

- Accounts/guest sessions, ownership, CSRF/session security, retention and durable deletion.
- PDF/DOCX/TXT/HTML uploads, pasted text, encrypted originals, hashes and mapped token-aware chunks.
- Secure policy discovery, source selection, capture metadata and explicit missing/inaccessible categories.
- Gemini/Groq/OpenRouter adapters, structured validation, explicit routing consent and usage metadata.
- Separate generation, exact source checks and semantic/context review; supported/partial/unsupported/ambiguous states.
- PostgreSQL jobs, actual progress, cancellation/retry, retained findings, conversations and encrypted reports.
- Source highlighting, Evidence Passports, server search/pagination, source-grounded Q&A and abstention.
- Real dashboard/library counts, display-name changes and retained-text comparison.
- Optional scoped read-only private MCP adapter; public OAuth is not implemented.

See [requirements audit](docs/REQUIREMENTS_AUDIT.md) and [executed verification](docs/VERIFICATION.md). Production readiness is not claimed.

## Stack and architecture

React19, TypeScript, Vite, Tailwind, TanStack Query and Lucide; Python 3.12?3.13, FastAPI, Pydantic, SQLAlchemy2, Alembic and PostgreSQL16+. PyMuPDF/python-docx/BeautifulSoup extract text; tiktoken measures chunks. Tests use pytest, Vitest, ESLint and Playwright.

```text
Browser -> authenticated API -> PostgreSQL + encrypted private storage
                               -> durable job -> separate worker
Extraction -> mapped chunks -> selected provider -> exact + semantic review
Persisted findings -> source viewer / grounded Q&A / reports
```

REST and MCP reuse authorization/application services. No Redis/vector DB/microservices are required.

```text
backend/app/          API, models, config, security, worker, providers, services
backend/migrations/  reviewed Alembic revisions
backend/tests/       synthetic fixtures and integration/security/provenance tests
frontend/src/        application, feature pages, shared components and styles
frontend/e2e/        isolated regressions and explicit live browser scenario
scripts/test_e2e.py   temporary browser-test service orchestration
docs/                specs, audit, verification, deployment and OpenAPI
compose.yml          optional local PostgreSQL service
HOW_TO_RUN.md        exact commands, user journey and troubleshooting
```

## Installation and running

Requirements: Python 3.12?3.13, Node22.12+ or24+, and reachable PostgreSQL. **Preserve existing backend/.env; never copy a template over it.** For a new checkout only, create that file privately from placeholders if absent.

```powershell
py -3.13 -m venv .venv        # only if missing
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.lock
python -m pip install --no-deps -e backend
cd frontend
npm ci
cd ../backend
python -m app.manage migrate
python -m app.manage check
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Second terminal from root: `cd backend`, then `..\.venv\Scripts\python.exe -m app.worker`.

Third terminal from root: `cd frontend`, then `npm run dev -- --strictPort`.

**App: http://localhost:5173**. **API: http://127.0.0.1:8000/docs**; live schema `/openapi.json`. `/api/v1/ready` checks DB connectivity. [HOW_TO_RUN.md](HOW_TO_RUN.md) explains every workflow and failure recovery.

## PostgreSQL and environment

The runtime requires PostgreSQL. Plain postgresql:// and postgres:// URLs normalize internally to psycopg; no secret file is rewritten and no SQLite fallback occurs. Explicit isolated tests alone may use SQLite. A configured remote database needs no local service. For a new local database, configure root compose placeholders privately, run `docker compose up -d`, and supply its URL in backend/.env.

API and worker must share configuration/storage. Run Alembic upgrades and `alembic check`; never reset existing data to fix migrations. Added revisions create the storage-deletion outbox and retained report metadata without dropping tables.

| Variables | Purpose |
|---|---|
| DATABASE_URL | Private PostgreSQL URL, preserving required TLS parameters. |
| ENVIRONMENT | development/production or explicit isolated test mode. |
| STORAGE_KEY / STORAGE_PATH | Stable Fernet key and private persistent volume. |
| SECURE_COOKIES / ALLOWED_ORIGINS / PUBLIC_URL | Session HTTPS behavior, browser origins and email links. |
| MAX_UPLOAD_BYTES / MAX_PAGES / MAX_DOCUMENT_TOKENS | Ingestion budgets. |
| GEMINI_API_KEY/MODEL, GROQ_API_KEY/MODEL, OPENROUTER_API_KEY/MODEL | Backend-only provider configuration. |
| PROVIDER_PRICING | Optional current price estimates; no invented free entitlement or spend guarantee. |
| SMTP_HOST/PORT/USER/PASSWORD, MAIL_FROM | Verification and recovery delivery. |
| MCP_BEARER_TOKEN / MCP_USER_ID / MCP_TOKEN_EXPIRES_AT / MCP_SCOPES | Optional private MCP process environment. |

`python -m app.manage providers` checks catalogs without printing keys/model configuration. Availability does not guarantee quota. Analysis requires explicit external-processing consent; confidential mode blocks transfer. Preferences never silently authorize fallback. Development without SMTP verifies locally; production registration requires delivery.

## Tests

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
..\.venv\Scripts\python.exe -m ruff check app tests
..\.venv\Scripts\python.exe -m alembic check
cd ../frontend
npm run lint
npm test
npm run build
npm run test:e2e
```

The browser harness uses temporary storage/database and disabled providers on8002/5174, then stops its own processes. Live tests are opt-in, consume provider quota and preserve synthetic PostgreSQL rows. See HOW_TO_RUN. Reports distinguish mocked, live and unverified checks; passing synthetic tests is not a semantic accuracy benchmark.

## Privacy, deployment and limitations

Passwords use Argon2. HttpOnly SameSite sessions, CSRF/Origin checks and resource ownership/expiry guard private data. Sources and retained reports are encrypted. Deletion revokes access transactionally and queues physical removal for retry; content-free audits and separately governed backups have different retention. Local deletion cannot control provider retention.

Jobs use DB claims, leases and heartbeats. Interrupted generation fails explicitly; manual retries may repeat provider usage. Per-call resume and enforceable monetary ceilings remain incomplete. Large-source context limits can produce ambiguity/abstention.

OCR, expert review, semantic conflict detection, change alerts, trusted timestamps, S3 storage, public MCP OAuth and institutional SSO remain unimplemented. Human evidence evaluation, full accessibility/security review, parser isolation, backup restore and production operations need qualification.

Deployment uses static frontend hosting, HTTPS API, PostgreSQL, a private persistent volume and supervised worker. Production requires secure cookies/stable key. Restrict database/OS privileges; never expose storage or secrets through static hosting. See [deployment](docs/DEPLOYMENT.md). No cloud deployment is claimed.

## MCP and contribution

The pinned MCP SDK exposes five read-only private tools: list_my_documents, get_document_sections, search_document_clauses, get_evidence_passport and get_analysis_report. Configure a strong expiring bearer, fixed verified account and explicit read scopes in the process environment, then run `python -m uvicorn app.mcp_server:create_app --factory --host 127.0.0.1 --port 8001` from backend/. Endpoint: `/mcp`. Pass the bearer through the client's secret manager, never a URL/frontend. This adapter refuses production; public OAuth/interoperability remains a release gap.

Use cohesive modules, strict schemas, shared authorization and preserved source offsets. Add meaningful negative tests and update audit/OpenAPI for contract changes. Review migrations; do not fix schema drift destructively. Keep .env, runtime storage and test artifacts ignored. Avoid infrastructure without a concrete requirement.

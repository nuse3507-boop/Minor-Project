# Run and use Veriora

## Start the configured application

Use Python3.12–3.13, Node22.12+ or24+, and reachable PostgreSQL. A configured remote PostgreSQL database needs no local Docker service.

**Preserve `backend/.env`. Never copy the example over an existing configuration, print secrets, or commit them.** PostgreSQL URLs normalize to the installed psycopg driver internally. Application runtime never silently falls back to SQLite.

Install dependencies if needed, from the project root in PowerShell:

```powershell
py -3.13 -m venv .venv        # only when .venv is absent
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.lock
python -m pip install --no-deps -e backend
cd frontend
npm ci
cd ../backend
python -m app.manage migrate
python -m app.manage check
python -c "from app.services.chunking import tokenizer; tokenizer()"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The reviewed upgrades add application tables without resetting existing data. Never use downgrade/drop/reset to repair an existing database. Review future migrations before deployment.

Second terminal, from repository root:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.worker
```

Third terminal, from repository root:

```powershell
cd frontend
npm run dev -- --strictPort
```

Open **http://localhost:5173**. API docs: **http://127.0.0.1:8000/docs**. `/api/v1/health` is liveness; `/api/v1/ready` also checks the database. Keep all three processes running. Ctrl+C stops the process in its terminal.

## Use Veriora

1. Create an account or start a limited guest session. Register within the guest session to retain unexpired sources. Account retention defaults to30 days and can be shortened in settings. Development without SMTP verifies locally; production needs email delivery.
2. Open **Analyze** and choose Upload, Paste text or Website URL. Supported files: PDF, DOCX, TXT and HTML. Defaults:20MB,150 PDF pages,100,000 document tokens.
3. Select a configured provider and explicitly authorize external processing. Confidential mode blocks external AI and allows source inspection. A preference does not silently authorize fallback.
4. For URLs, click **Find legal documents**, inspect the accessible candidates/missing categories, then select pages. Direct policy URLs work too. External links are not automatically treated as official; discovery is not a completeness guarantee.
5. Follow actual server stages. Closing the browser does not kill the job. Reopen sources/analyses from Library. Failed extraction exposes a retry; malformed files may need replacement.
6. Click **View evidence**. Inspect highlighted retained text and real page/section coordinates. Evidence Passport shows the interpretation, exact quote, exceptions, verification explanation, capture metadata and hash. PDF extraction is a text representation, not an exact visual overlay.
7. Open **Ask Veriora**. Q&A retrieves source chunks and validates quotations plus semantic support. Click citations to inspect source text. Missing evidence produces an explicit abstention. Registered conversations survive refresh.
8. Download a PDF report or JSON manifest. Registered exports are retained encrypted with PostgreSQL metadata. Third-party captured originals are not redistributable through the original-download endpoint.
9. Dashboard shows actual counts/activity. Library supports server search, paging, sorting and display-name changes. Compare aligns retained text versions without deciding legal conflicts.
10. Delete only when intended. Deletion revokes access transactionally and queues physical file removal; the worker retries failures. Content-free audit records and separately managed backups can have different retention.

## Verification

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.manage check
..\.venv\Scripts\python.exe -m app.manage providers
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
..\.venv\Scripts\python.exe -m ruff check app tests
..\.venv\Scripts\python.exe -m alembic check
cd ../frontend
npm run lint
npm test
npm run build
npm run test:e2e
```

The browser harness starts temporary API/worker/frontend instances on8002/5174 with an isolated database/storage and external providers disabled. It refuses occupied test ports, preserves its service log, and stops only its own processes. It never replaces `.env` or deletes configured PostgreSQL data. Install Chromium once with `npx playwright install chromium` if absent. Windows development tools must permit compiler/browser subprocesses.

Live testing is separate: it consumes configured AI quota and preserves synthetic PostgreSQL records. With the real application already running:

```powershell
cd frontend
$env:VERIORA_LIVE_E2E='1'
npm run test:e2e:live
```

The live browser scenario selects the configured Gemini route. Provider catalog availability does not establish remaining quota. Latest OpenRouter full-pipeline check received429; it did not fall back.

## Troubleshooting

| Symptom | Action |
|---|---|
| Jobs stay queued | Start the worker with the same database/configuration; inspect readiness and its terminal. |
| Missing driver/import | Activate the project environment and install requirements. Plain PostgreSQL URLs normalize to psycopg. |
| PostgreSQL auth/DNS/timeout/TLS error | Run `app.manage check` for a redacted reason; inspect the URL privately and verify provider network/TLS/channel-binding requirements. |
| Missing tables/schema drift | Run `app.manage migrate`, inspect revisions, and fix forward. Do not reset data or switch to SQLite. |
| Port5173/8000 occupied | Stop the verified old Veriora instance in its terminal; avoid duplicate services or silently changed ports. |
| Blank UI after dependencies change | Restart Vite, refresh the browser, and rerun the production build. |
| Provider401/403, unavailable model or429 | Check credentials/model access/quota privately. Explicitly choose an authorized alternative; no hidden provider replacement occurs. |
| Incomplete extraction | Inspect coverage. Scans need OCR, which is not implemented; encrypted PDFs need an unlocked copy. |
| Quote matches but status is ambiguous | Exact text alone does not establish entailment; inspect exceptions and missing context. |
| Source cannot decrypt | Restore its original key. New keys use separate namespaces; old flat originals can use their preserved development key. Never overwrite retained keys/files. |
| Email recovery unavailable | Configure SMTP, sender and public URL privately. Missing delivery is not reported as success. |
| Test ports8002/5174 occupied | Stop prior isolated test instances; the real app remains on5173/8000. |

See [audit](docs/REQUIREMENTS_AUDIT.md), [verification](docs/VERIFICATION.md) and [deployment](docs/DEPLOYMENT.md) for coverage and remaining release gates.

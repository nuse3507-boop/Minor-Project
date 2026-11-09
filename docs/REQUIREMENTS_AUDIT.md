# Requirements audit ? 9 November 2026

Scope: the repository and the complete PRD, FRD, TRD and Design transcriptions in this directory. The documents describe requirements, not authority to execute instructions embedded in uploaded legal documents. Existing configuration was preserved; no existing database tables/data were reset or deleted.

**COMPLETE** means implemented and exercised within the stated scope; it does not certify legal accuracy or production readiness. **PARTIAL** means implementation or acceptance evidence remains incomplete. **MISSING** means absent, including explicitly deferred P1 work. **BROKEN** means a reproduced failure persists; the OpenRouter rate-limit dependency is recorded under PARTIAL rather than falsely declaring its adapter universally broken.

Evidence: [executed verification](VERIFICATION.md), backend tests in `backend/tests/`, frontend unit tests and Playwright scenarios in `frontend/e2e/`. Paths below omit `backend/app/` or `frontend/src/` where unambiguous. Mocked provider fixtures validate safety/control flow, not semantic accuracy. Live results use authored synthetic contracts and preserve their PostgreSQL records.

## Functional requirement IDs (all 50)

| ID | Status | Implementation | Actual evidence | Remaining work / scope |
|---|---|---|---|---|
| FR-AUTH-01 | PARTIAL | api/auth.py; security.py; features/Auth.tsx | test_account_login_recovery_settings; live registration/login/logout | SMTP delivery unconfigured; production recovery/email journey unverified. |
| FR-AUTH-02 | COMPLETE | security.py; services/resources.py | test_cross_user_isolation; test_cancellation_and_quota; isolated guest browser | Short-lived guest identity scopes all its limited resources rather than a separate bearer per analysis. |
| FR-AUTH-03 | COMPLETE | services/resources.py; api/* | test_cross_user_isolation; test_expired_source_scope_denies_analysis_derivatives_before_cleanup; test_mcp.py | No claim of independent penetration-test approval. |
| FR-AUTH-04 | PARTIAL | services/resources.py; models.py StorageDeletion; worker.py | test_deletion_rollback_preserves_original_until_committed; test_file_deletion_failure_is_pending_not_false_success | Source deletion returns pending on physical failure. Account deletion response still needs equivalent pending indication; backup/audit retention is operational. |
| FR-ING-01 | COMPLETE | api/documents.py; services/ingest.py; features/Intake.tsx | test_reject_unsafe_or_mismatched_files; live PDF upload; isolated paste/upload | Scans require OCR; no OCR claim. |
| FR-ING-02 | COMPLETE | config.py; services/ingest.py; worker.py | test_size_limit_enforced_before_parser; test_scan_only_pdf_and_encrypted_pdf_rejected; chunk token tests | Reverse proxy must enforce streaming request/body deadlines in deployment. |
| FR-ING-03 | COMPLETE | models.py Source; services/storage.py; worker.py | test_ingest_persistence_original_hash_and_delete; test_source_ids_do_not_collide_for_duplicate_content | Immutable original/version retained; rename changes display title only. |
| FR-ING-04 | COMPLETE | services/ingest.py; services/verification.py | test_text_unicode_identity_offsets; test_docx_preserves_table_and_paragraph_order; PDF coordinate test | PDF viewer displays mapped extracted text, not exact original glyph geometry. |
| FR-ING-05 | COMPLETE | services/ingest.py; worker.py; CoverageNotice.tsx | test_pdf_missing_text_pages_disclosed_and_real_page_coordinates; test_unreadable_pages_never_get_unqualified_supported_status | Detection cannot establish that every meaningful visual element was extracted. |
| FR-ING-06 | COMPLETE | services/chunking.py; models.py Chunk | test_chunking_long_clause_no_loss_and_token_bound; test_oversized_sentence_and_unicode_token_split_preserve_text; test_clauses_not_split_unnecessarily_and_pages_preserved | No fabricated clause/page labels. |
| FR-ING-07 | MISSING | Extraction explicitly rejects scan-only input | test_scan_only_pdf_and_encrypted_pdf_rejected | P1 OCR adapter, confidence and estimated geometry absent. |
| FR-URL-01 | COMPLETE | services/discovery.py | unsafe URL, private DNS, mixed DNS, redirect and pinned-address tests in test_processing.py | Deployment-network SSRF review remains a release gate. |
| FR-URL-02 | PARTIAL | services/discovery.py; api/documents.py | test_discovery_records_missing_inaccessible_and_duplicate_policies; test_sitemap_parsing_is_bounded_and_rejects_entities; live Mozilla discovery | Bounded same-site links/sitemap only; external official locations and JS-rendered navigation not fully supported. |
| FR-URL-03 | PARTIAL | services/discovery.py; features/Intake.tsx | discovery fixture; live 15 candidates/13 accessible | Candidate provenance/status shown; no calibrated discovery confidence score. |
| FR-URL-04 | COMPLETE | services/discovery.py; features/Intake.tsx | discovery missing/inaccessible fixture; live missing-category response | Never guarantees complete legal corpus discovery. |
| FR-URL-05 | COMPLETE | services/discovery.py; worker.py; models.py Source | test_capture_retry_reuses_saved_original_after_extraction_failure; discovery and ingestion tests | Stores available response metadata, bytes/hash and URL provenance. |
| FR-URL-06 | PARTIAL | services/discovery.py; consent schemas | bounded fetch/sitemap tests; robots handling in implementation | No CAPTCHA/login bypass. Exhaustive site-terms assessment is outside automated discovery; deployed-network rate policy needs qualification. |
| FR-URL-07 | PARTIAL | api/comparisons.py; services/comparison.py; features/Compare.tsx | test_comparison.py; isolated account/compare browser | Manual captures and text diffs work; scheduled monitoring, effective-date extraction and alerts absent. |
| FR-AI-01 | COMPLETE | services/analysis.py; schemas.py | test_valid_source_requires_separate_semantic_review; live Gemini/Groq findings | Categories validated by schema; not an accuracy benchmark. |
| FR-AI-02 | COMPLETE | services/analysis.py; models.py Finding/ProviderCall | test_integrated_analysis_reports_qa_delete; duplicate trace test | Records prompt/provider/requested and actual model, source/chunk/candidate metadata. |
| FR-AI-03 | COMPLETE | services/analysis.py prompts; provider schemas | test_question_answer_requires_semantic_support; live scoped Q&A | No external legal research mode enabled. |
| FR-AI-04 | COMPLETE | services/verification.py; worker.py | test_forged_citations_never_verified; test_false_citations_never_valid; repeated-quote test | Worker revalidates citations before persistence. |
| FR-AI-05 | PARTIAL | services/analysis.py semantic verifier | test_quote_match_does_not_entail_statement; test_semantic_failure_is_visible_ambiguous; live Gemini/Groq | Separate review works; human-labeled semantic accuracy/calibration not established. |
| FR-AI-06 | COMPLETE | services/verification.py; lib/evidence.ts; Workspace.tsx | test_exact_quote_is_not_semantic_support; frontend evidence tests; workspace browser | Invalid locations never receive verified label/highlight. |
| FR-AI-07 | COMPLETE | services/analysis.py; Workspace.tsx | forged/ambiguous backend tests; workspace invalid citation browser | Rejected candidates remain visible with explanations. |
| FR-AI-08 | COMPLETE | services/analysis.py aggregation | test_duplicate_findings_preserve_candidate_trace | Normalized duplicate removal preserves original candidates; no semantic conflict claim. |
| FR-AI-09 | PARTIAL | services/analysis.py global context review | test_missing_exception_downgrades_supported_verdict; test_semantic_review_receives_distant_exception; context-limit test | Bounded global context; ambiguity when complete context cannot fit. Missing appendix detection is model-dependent. |
| FR-AI-10 | COMPLETE | worker.py; services/analysis.py; CoverageNotice.tsx | test_partial_generation_reports_uncovered_chunks_and_sections; unreadable-page test | Discrete actual stages/counts; no artificial progress percentage. |
| FR-AI-11 | PARTIAL | providers/*; services/analysis.py; config.py | adapter/retry/consent tests; three live probes; Gemini/Groq full pipeline | OpenRouter full schema returned429. Separate role-model UI, hard spend ceiling and per-call resume incomplete. |
| FR-AI-12 | COMPLETE | providers/base.py; models.py ProviderCall | test_adapters_normalize_structured_outputs; live token/latency metadata | Pricing estimates only when configured; no guarantee of free service. |
| FR-AI-13 | COMPLETE | schemas.py; lib/evidence.ts; Evidence Passport | frontend evidence tests; live Passport | Qualitative support explanations; no fabricated confidence percentage. |
| FR-AI-14 | COMPLETE | services/analysis.py | test_no_supported_evidence_abstains_without_provider_call; test_question_answer_with_forged_citation_abstains | Abstention distinguishes missing evidence from absence of a provision. |
| FR-AI-15 | MISSING | Text comparison is not semantic conflict detection | test_comparison.py covers text only | P1 cross-document conflict verifier absent. |
| FR-AI-16 | MISSING | No active review route | Not tested; absent on inspection | P1 expert approve/reject/rewrite and immutable review history absent. |
| FR-QA-01 | COMPLETE | services/retrieval.py; services/analysis.py; api/analyses.py; QuestionPanel.tsx | test_source_question_can_use_verified_evidence_without_prior_findings; PostgreSQL native retrieval test; live Q&A/citation navigation | Answer sources not restricted to prior findings. |
| FR-QA-02 | COMPLETE | services/analysis.py; QuestionPanel.tsx | forged answer/semantic failure tests; isolated workspace abstention browser | No invented missing terms. |
| FR-QA-03 | PARTIAL | services/analysis.py answer semantic review | test_question_answer_requires_semantic_support; exception tests | Conservative context cap; human exception/contradiction benchmark pending. |
| FR-QA-04 | COMPLETE | models.py Conversation; api/analyses.py; QuestionPanel.tsx | test_integrated_analysis_reports_qa_delete; live refresh/history | Registered conversations retained; guest UI cache is transient. |
| FR-UI-01 | PARTIAL | SourceViewer.tsx; Workspace.tsx | live PDF evidence highlight; workspace invalid-location browser | Exact retained-text highlights and real page anchors work; original PDF geometry overlay absent. |
| FR-UI-02 | COMPLETE | api/analyses.py; Workspace.tsx; lib/query.ts | integrated API tests; navigation unit tests; workspace browser | Server filters/pagination; category/status/source/query in URL. |
| FR-UI-03 | COMPLETE | api/dashboard.py; features/Dashboard.tsx; Library.tsx | test_dashboard_pagination_and_display_only_rename; live dashboard/library | Real counts/activity only. |
| FR-UI-04 | PARTIAL | worker.py; SourcePage.tsx; Workspace.tsx; ui.tsx | cancellation/expired lease/retry tests; core browser | Core state paths tested; not every provider/browser interruption combination exhaustively verified. |
| FR-UI-05 | PARTIAL | Tabs.tsx; SourceViewer.tsx; styles.css | navigation.test.tsx; 320px/mobile browsers; axe public pages | Full screen-reader, keyboard-only journey, tablet and200% zoom audit pending. |
| FR-EXP-01 | COMPLETE | api/analyses.py; services/reports.py; models.py Report | test_integrated_analysis_reports_qa_delete; live PDF download | Encrypted report retained with DB metadata; not legal certification. |
| FR-EXP-02 | COMPLETE | services/reports.py; api/analyses.py | integrated manifest hash assertion; live JSON download | Source IDs/hashes/coordinates/provider and limitation metadata included. |
| FR-EXP-03 | COMPLETE | api/documents.py; services/resources.py | test_cross_user_isolation; original hash test; URL original-download restriction | Third-party captured originals not redistributable through download endpoint. |
| FR-EXP-04 | PARTIAL | services/resources.py; StorageDeletion; worker.py | test_delete_source_removes_derived_analysis_findings_and_original; rollback/outbox tests | Source/account cascade implemented; standalone analysis-deletion UI/API absent. Physical cleanup failures queue retries. |
| FR-EXP-05 | MISSING | Hashes/capture dates are not trusted timestamps | No trusted timestamp test; absent on inspection | P1 signed/timed evidence bundle and chain-of-custody process absent. |
| FR-CMP-01 | PARTIAL | services/comparison.py; api/comparisons.py; features/Compare.tsx | test_comparison.py; isolated compare browser | Aligned retained-text diff works; semantic alignment and effective/observed chronology incomplete. |
| FR-REV-01 | MISSING | No reviewer feature enabled | Absent on inspection | P1 reviewer identity/sign-off/audited decisions absent. |

## Architecture and product decisions

| ID | Status | Code / exercised evidence | Remaining work |
|---|---|---|---|
| ADR-01 | COMPLETE | frontend/package.json, src/app/App.tsx; TypeScript/build and browser tests | None for chosen stack. |
| ADR-02 | PARTIAL | Lucide, ui.tsx, Tabs.tsx; axe and tab unit tests | Complete manual accessibility qualification. |
| ADR-03 | COMPLETE | backend/pyproject.toml, app/main.py, schemas.py;118 backend tests | No stack gap. |
| ADR-04 | COMPLETE | db.py, models.py, migrations/; live PostgreSQL18, four upgrades, alembic check, native FTS/FK integration | Backup restore qualification separate. |
| ADR-05 | PARTIAL | worker.py; cancellation/lease/retry tests; real worker processed PDF | Two-worker contention/load qualification and per-call checkpointing pending. |
| ADR-06 | PARTIAL | storage.py; encrypted filesystem tests and retained report roundtrip | S3-compatible production adapter absent. |
| ADR-07 | PARTIAL | providers/*; all three live simple probes, Gemini/Groq full schema | OpenRouter full schema blocked by429. |
| ADR-08 | PARTIAL | retrieval.py; native PostgreSQL FTS/ownership rollback integration | GIN optimization and measured recall benchmark pending. |
| ADR-09 | PARTIAL | ingest.py, verification.py; format/offset tests and live PDF highlight | Retained-text navigation implemented; original PDF geometry UI incomplete. |
| ADR-10 | PARTIAL | mcp_server.py, tests/test_mcp.py | Private scoped read-only adapter only; production OAuth/client interoperability qualification absent. |
| ADR-11 | PARTIAL | /api/v1, schemas.py, docs/openapi.json; snapshot test | Remaining untyped message/export dictionaries and SDK contract generation can improve. |
| ADR-12 | PARTIAL | security.py, resources.py, discovery.py; ownership/SSRF/CSRF tests | Independent review, parser sandbox, deployed least privilege and operational tests pending. |
| DEC-01 | COMPLETE | Document-only prompts/copy and explicit disclaimers; semantic negative tests | No governing-law opinions enabled. |
| DEC-02 | COMPLETE | FastAPI/PostgreSQL/dedicated worker; live full browser flow | None for selected architecture. |
| DEC-03 | PARTIAL | Configured provider adapters, consent and telemetry | OpenRouter quota and current deployment privacy terms require qualification. |
| DEC-04 | PARTIAL | Encrypted local persistent-volume adapter | Private object storage remains absent. |
| DEC-05 | COMPLETE | Guest issuance/quota/expiry and account upgrade tests | Public deployment abuse controls require qualification. |
| DEC-06 | COMPLETE | Scanned PDF rejection/coverage tests; OCR explicitly deferred | P1 OCR remains missing, as decided. |
| DEC-07 | PARTIAL | Shared REST authorization and private MCP tests | P1 public authorized MCP integration not released. |
| DEC-08 | COMPLETE | Current accessible snapshots retained; discovery tests | P1 historical archive/change monitoring not claimed. |
| DEC-09 | COMPLETE | Live PDF/JSON downloads; ownership/license original restriction; retained report roundtrip | No admissibility claim. |

## Acceptance scenarios

| ID | Status | Executed evidence / gap |
|---|---|---|
| AT-01 | PARTIAL | DOCX paragraph/table extraction and source validation tests pass; live numbered-DOCX AI browser scenario not executed. |
| AT-02 | COMPLETE | Parameterized forged page/offset/source tests and invalid-location browser scenario pass. |
| AT-03 | COMPLETE | Missing-exception downgrade and distant-exception semantic fixtures pass; not a human accuracy benchmark. |
| AT-04 | COMPLETE | Discovery fixture records403/inaccessible and missing categories. |
| AT-05 | PARTIAL | HTML passive extraction test passes; prompts delimit untrusted text, no execution tools exposed. Adversarial model benchmark pending. |
| AT-06 | COMPLETE | Cross-user/session isolation tests pass. |
| AT-07 | COMPLETE | Deletion/cascade/outbox rollback and pending-failure tests pass; isolated browser deletes only synthetic test data. |
| AT-08 | COMPLETE | Partial generation fixture identifies uncovered chunks after provider failure; actual OpenRouter429 classified without replacement. |
| AT-09 | COMPLETE | Duplicate findings preserve original candidate trace in test_ai.py. |
| AT-10 | PARTIAL | Unsupported and forged-answer abstention tests pass; exact retention-period natural-language fixture/human evaluation pending. |
| AT-11 | PARTIAL | Global context and missing-exception controls tested; dedicated missing-appendix corpus not evaluated. |
| AT-12 | COMPLETE | Partial semantic state/explanation and frontend status mapping tests pass. |
| AT-13 | COMPLETE | Integrated manifest source hash assertion and live manifest download pass. |
| AT-14 | PARTIAL | Tab roving keyboard test and semantic buttons pass; complete mouse-free evidence journey not manually qualified. |
| AT-15 | COMPLETE | Scan-only PDF is rejected with OCR-required notice; no invented empty analysis. |

## Design packages and release milestones

| ID | Status | Evidence and remaining work |
|---|---|---|
| DS-01 | PARTIAL | Central neutral/teal tokens, Lucide, common dialogs/tabs, public axe checks; all-page manual contrast/focus audit pending. |
| DS-02 | PARTIAL | Live PDF upload and policy discovery; isolated text/guest/error flows; exhaustive input/browser matrix pending. |
| DS-03 | PARTIAL | Real split workspace, exact retained-text highlights, Passport, server filters, coverage; original PDF overlay/complete zoom controls absent. |
| DS-04 | COMPLETE | Live scoped Q&A, source navigation, refresh history, reports, dashboard/library and persisted settings; encrypted retained report integration passes. |
| DS-05 | PARTIAL | Automated axe on three public pages and320px/mobile browser checks pass; screen-reader,200% zoom, tablet and full keyboard manual audit pending. |
| G0 | PARTIAL | All four baseline documents transcribed/read and traced here; named product/design/security sign-off not supplied. |
| G1 | PARTIAL | PostgreSQL schema/migrations, encrypted originals, mapped chunks and durable jobs tested; production recovery/load gate pending. |
| G2 | PARTIAL | Live Gemini/Groq and deterministic/semantic safety fixtures pass; OpenRouter quota and independent labeled evaluation block verified-AI release qualification. |
| G3 | PARTIAL | Core application workflows run live and regressions pass; remaining FR partials above prevent blanket acceptance. |
| G4 | PARTIAL | Security negative tests, lint/build/axe and safe migration checks pass; SMTP, restore drills, independent security/accessibility/operations approval pending. |
| G5 | PARTIAL | Text comparison/private MCP implemented; OCR, expert review, semantic conflicts, trusted timestamps and monitoring absent. |

## Requirements without canonical IDs

PRD scope/non-functional goals, FRD sections7/9 and TRD operational/testing sections are covered as follows: durable stages/cancel/retry and provenance are tested; retry cannot promise free replay. English document-only interpretation is the supported scope. Pricing is optional estimated telemetry, not an enforceable spending cap. Latency/load/quality targets lack a representative benchmark. Database/volume encryption, backup retention, restore drills, deployed monitoring/alerting, production email and least-privilege infrastructure remain operator/release work. Settings expose actual retention/provider behavior; no pretend preferences or fabricated analytics are enabled. Original PDF rendering, trusted human review and the full manual WCAG2.2 AA journey remain incomplete.

No critical failure reproduced in the exercised core path remains open. This is not a claim that every requirement is complete or that production security/evidence accuracy has been certified. OpenRouter's full-schema429 is the current reproduced external dependency failure. No existing user documents were deleted to make tests pass.

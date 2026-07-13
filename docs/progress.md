# Progress

## Phase 6 final decision

- Lifecycle correction: COMPLETED; two external normal-PowerShell verifier runs exited 0 with cleanup passed.
- Decision: RELEASE_WITH_LIMITATIONS — Local OCR v0.1.0. Low-resolution input remains weak and requires manual verification.

## Phase 0 — Repository and environment

- Status: COMPLETED
- Files created: monorepo skeleton, FastAPI configuration/API, CUDA check, tests, setup documentation, minimal Next.js boot target.
- Commands executed: created Python 3.12 venv; installed backend/test dependencies; ran pytest; started Uvicorn; queried health/GPU endpoints; installed pnpm dependencies; built and started Next.js.
- Tests executed: backend pytest suite; Next.js production build; HTTP checks against backend and frontend.
- Test results: 7 passed; Next.js build compiled and generated 3/3 static pages; `/api/health`, `/api/system/gpu`, and frontend `/` returned successfully.
- Known issues: sandbox default temp/cache paths were not writable, so verification used project-local cache paths. Default system Python is 3.11.9; the project venv is Python 3.12.10.
- Next allowed phase: Phase 1.

## Phase 6 — OCR quality evaluation and release decision

- Status: COMPLETED
- Canonical decision dataset: 38 records (20 primary, 18 DPI); historical physical jobs: 44, with 12 historical DPI records excluded.
- Scoring: 83 scorer tests passed; page-aligned multi-page scoring, numeric fields, and table cells were evaluated.
- Manual review: 8 required documents reviewed with local Playwright Chromium screenshot evidence.
- Regressions: 139 backend tests, 3 frontend smoke checks, 4 Playwright tests, TypeScript, and direct workspace production build passed.
- Decision: REMAIN_RC — Local OCR v0.1.0-rc1. Low-resolution category median relaxed CER was 22.45%, above the 15% category threshold; the packaged verifier wrapper left scoped listener children without PID files and did not satisfy the final stop gate.

## Phase 1 — Real model inference spike

- Status: COMPLETED
- Files created: download and image/PDF smoke-test scripts.
- Commands executed: inspected NVIDIA driver; attempted official reported PyTorch 2.10.0 wheel; installed available CUDA 12.9 pair; ran CUDA check; downloaded and verified official snapshot; generated a local sample image; ran online-setup and offline-runtime image smoke tests.
- Tests executed: `scripts/check_cuda.py`; `scripts/smoke_test_image.py` twice, including with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.
- Test results: RTX 5070 detected with 12,226 MiB; setup smoke load 4.101 s, inference 2.683 s, peak allocated VRAM 7,204 MiB; offline smoke load 3.921 s, inference 2.559 s, peak allocated VRAM 7,204 MiB; Markdown output saved locally.
- Known issues: official model card reports PyTorch 2.10.0/torchvision 0.25.0, but that pair was unavailable from the official CUDA 12.9 index; verified successfully with 2.8.0+cu129/0.23.0+cu129. Upstream custom code warns about deprecated `torch_dtype`, an initialized `position_ids` buffer, and missing attention mask.
- Next allowed phase: Phase 2, but intentionally not started per initial-task scope.

## Phase 2 — OCR service core

- Phase: Phase 2 — OCR service core
- Status: COMPLETED
- Scope: SQLite image-job persistence, atomic storage, lazy local model service, single CUDA worker, image APIs, cancellation/retry/delete, restart recovery, fake-model tests, minimal frontend system status. No PDF pipeline or SSE.
- Files created: database base/session, OCR job model, job/model schemas, error contract, storage/validation/model/job services, OCR worker, job API, Phase 2 API verification script, and Phase 2 tests.
- Files modified: backend configuration/dependencies/lifespan/system API, minimal frontend status page, README, architecture/API/Windows setup/troubleshooting/progress documentation.
- Commands executed: inspected repository and installed versions; queried Context7 for SQLAlchemy 2.0 transactions and FastAPI 0.116.1 lifespan; installed SQLAlchemy 2.0.41 and python-multipart 0.0.20; compiled Python; ran pytest; started Uvicorn with offline environment variables; ran two API uploads and polling/result checks; inspected output files/logs; built frontend.
- Automated tests: 28 passed in 3.15 seconds. Tests use unique project-local data directories, temporary SQLite databases, and a fake model; no real model loads in pytest.
- Real GPU verification: two API-to-worker-to-GPU jobs completed on NVIDIA GeForce RTX 5070. First submit 16 ms; health during load 5 ms. Second submit 4 ms; health during inference 3 ms. Both persisted Markdown, TXT, and JSON.
- Offline verification: backend ran with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, telemetry disabled, local snapshot path, and `local_files_only=True`; both jobs completed.
- Measured model load time: 6,519 ms on first job only.
- Measured image-job inference time: first image 2,709 ms; second image 2,223 ms.
- Measured peak VRAM: first 7,204 MiB; second 7,213 MiB.
- Known issues: trusted upstream code emits `torch_dtype`, `position_ids`, and attention-mask warnings. Active cancellation is cooperative and cannot interrupt a running GPU call. Shutdown verification used TestClient for graceful lifespan and forced termination only to clean up the separately launched verification server.
- Acceptance criteria: all 24 Phase 2 criteria passed, including persistent job ID, non-blocking upload, SQLite state, single worker, responsive health endpoint, lazy/reused model, atomic outputs, query/result/cancel/retry/delete, recovery, failure survival, tests, two offline real GPU jobs, measurements, no PDF pipeline, and documentation.
- Next allowed phase: Phase 3 PDF pipeline only; not started.

## Phase 3 — Reliable PDF OCR pipeline

- Phase: Phase 3 — Reliable PDF OCR pipeline
- Status: COMPLETED
- Scope: additive PDF validation, fixed DPI selection, page persistence, lazy sequential render/OCR, page progress/APIs, combined outputs, failure isolation, cancellation/retry/recovery, polling UI, fake-model tests, and real offline RTX 5070 verification. No SSE or Phase 4 work.
- Files created: OCR page model/schema, versioned SQLite migration, PDF service, PDF migration/validation/worker tests, and `scripts/verify_phase3_pdf.py`.
- Files modified: OCR job model/schema/repository/API/worker, storage/lifespan, minimal Next.js page, README, architecture/API/setup/troubleshooting/progress documentation.
- Database migration: schema version 3 ran twice idempotently against the existing `data/app.db`; both Phase 2 PNG records remained readable and were backfilled with derivable one-page completion metrics. `ocr_pages` uniqueness, foreign-key cascade, and required indexes were verified.
- Commands executed: inspected repository/progress/live SQLite; queried Context7 PyMuPDF guidance; compiled backend; ran migration twice; inspected migrated rows/indexes; ran full pytest suite; built Next.js; started offline Uvicorn twice; generated/uploaded two three-page verification PDFs; polled job/page/health/model endpoints; fetched combined and page results; ran two real image regression jobs; inspected SQLite, files, combined Markdown/JSON, and logs; stopped verification servers.
- Automated tests: 46 passed in 6.05 seconds after the final output-format correction and explicit PDF job-retry/missing-source cases. Tests use project-local isolated SQLite/data directories and a fake model; real model is not loaded by pytest.
- Image regression tests: fake-model image regression passed; two real offline image jobs also completed using the resident model at 2,259 ms and 2,115 ms inference with unchanged `loaded_at`.
- Real PDF GPU verification: final corrected three-page PDF job `19d56e42-f454-4621-8ab6-c0208e9f6d7e` completed on RTX 5070. All combined and individual page APIs/files passed, page text and boundaries remained ordered, and maximum simultaneous `PROCESSING` pages was one.
- Offline verification: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, telemetry disabled, local snapshot, and `local_files_only=True`; no external OCR API used.
- Test PDF page count: 3.
- Observed job transitions: `QUEUED → LOADING_MODEL → PROCESSING → COMPLETED`.
- Observed page transitions: each sampled page showed `PENDING → RENDERED → PROCESSING → COMPLETED`; `RENDERING` completed faster than the 50 ms polling interval and was persisted/tested but not observed in real polling.
- Upload latency: 15 ms.
- Total duration: 13,606 ms wall time including 6,646 ms initial model load; persisted summed render/inference duration 6,850 ms.
- Per-page rendering times: page 1 72 ms; page 2 71 ms; page 3 72 ms.
- Per-page inference times: page 1 2,565 ms; page 2 2,024 ms; page 3 2,046 ms.
- Peak VRAM: page 1 7,715 MiB; page 2 7,723 MiB; page 3 7,732 MiB; maximum 7,732 MiB.
- Partial failure verification: fake-model tests proved one failed page preserves successes, later pages continue, placeholders are emitted, and final status is `COMPLETED_WITH_ERRORS`; every-page failure becomes `FAILED`.
- Cancellation verification: queued PDF cancellation remains immediate; active fake inference finished page 1, preserved it, stopped before page 2, retained pending pages, and kept progress below 100%.
- Retry verification: both page retry and PDF job retry requeued only the failed page, increased inference calls by exactly one, preserved successful pages, regenerated combined output, and returned the parent to `COMPLETED`. Fully successful jobs remained non-retryable.
- Restart recovery verification: completed pages were preserved; active page reset to `PENDING` when no rendered image existed; parent requeued from the first unfinished page; generic missing-source recovery remains `FAILED/SOURCE_FILE_MISSING`; completed/cancelled jobs remain unchanged.
- Known issues: active CUDA calls cannot be interrupted; `RENDERING` may be too brief for polling clients to observe; trusted upstream dtype/position/attention-mask warnings remain non-fatal; page images and upstream debug artifacts are intentionally retained; health worst sampled latency during real processing was 537 ms.
- Acceptance criteria: all 41 Phase 3 criteria passed, including migration preservation, image compatibility, PDF validation/encryption rejection, sequential page persistence/inference, progress, combined order/errors, failure isolation, cancellation/retry/recovery, full tests/build, real three-page offline GPU completion, responsive health, metrics, no external API, no SSE, and no Phase 4 work.
- Next allowed phase: Phase 4 reliability only; not started.

## Phase 4 — Operational reliability and stability hardening

- Phase: Phase 4 — Operational reliability and stability hardening
- Status: COMPLETED
- Scope: observable heartbeat/state, queue admission, disk preflight, SQLite hardening, integrity, manual cleanup/orphans, long PDF soak, queue, safe restart, resource/latency evidence, and minimal operational UI. No SSE, WebSockets, or Phase 5 work.
- Files created: reliability schemas/service, maintenance API, reliability tests, and Phase 4 soak/queue/restart verification scripts.
- Files modified: configuration, SQLite session, worker, job admission/API/system endpoints/lifespan, frontend status page, environment example, and all operational documentation.
- Configuration added: worker poll/heartbeat/stale intervals, busy timeout/WAL, queue cap, disk threshold, disabled-by-default cleanup/retention controls, shutdown grace, and health target.
- Database changes: no schema recreation or destructive migration. Existing Phase 2/3 records remained readable; SQLite connection pragmas verified through SQLAlchemy as WAL, foreign keys enabled, and 5,000 ms busy timeout.
- Commands executed: inspected progress/schema/filesystem; queried Context7 SQLAlchemy SQLite guidance; ran full tests; built frontend; started offline API; ran 12-page soak, three-job queue, safe restart, cleanup preview/run, integrity checks; inspected output/database state; stopped test servers.
- Automated tests: 56 passed in 8.33 seconds after all Phase 4 code/frontend changes; covered heartbeat/state, queue capacity, disk preflight, pragmas, integrity failures, cleanup, orphans, idempotency, and previous image/PDF regression suite.
- Regression tests: existing image/PDF, page retry, job retry, cancellation, migration, and recovery tests remained included in the complete suite.
- Long PDF verification: 12-page offline PDF job `1821e4b3-0224-4381-a384-18f7d3a8714e` completed with valid integrity and ordered page records.
- Queue verification: final three submissions completed in exact FIFO claim order `9ba24926-627f-4dfa-abc8-f0c4cc52178b`, `e6b64545-420f-415f-aa4a-457e26a903d8`, `2a91c30d-1b36-45c1-92b4-880231f9f9a2`; total queue duration was 18,409 ms and outputs were isolated.
- Restart verification: job `a63016eb-619f-4440-9875-f4ab550717fb` completed page 1, shut down normally at a page boundary, restarted, preserved page 1, completed pages 2–5, passed integrity, and worker returned `IDLE`.
- Cleanup verification: preview considered 11 terminal jobs and deleted nothing; rendered-page-only run removed 28 files / 2,005,799 bytes across 6 directories with zero failures. Sources, combined outputs, model files, and database records were preserved; soak result integrity remained valid.
- Worker heartbeat verification: fake long inference tests verified updates independent of OCR work; system endpoint exposes state, active job/page, queue, RAM, VRAM, counters, and last error without model loading.
- Upload latency: soak 22 ms; final queue jobs 38/15/12 ms.
- Health latency: soak p50 1 ms; p95 4 ms; maximum 373 ms. Final queue maximum 390 ms. No request timed out; p95 is below the 250 ms target and no health request exceeded 1,000 ms.
- Total processing duration: 12-page soak 44,258 ms, including initial model load.
- Per-page inference duration: first 2,660 ms; remaining pages 1,793–1,816 ms.
- Peak VRAM: 7,755 MiB.
- Process RSS: peak 7,359,299,584 bytes.
- Queue order observed: FIFO submission/claim order above; one worker owns GPU work.
- Restart states observed: active job persisted, completed page preserved, recovery requeued unfinished pages, final `COMPLETED` and worker `IDLE`.
- Cleanup bytes reclaimed: 2,005,799 bytes.
- Integrity verification: valid soak and restart PDF jobs returned no issues; missing Markdown and invalid JSON were detected in fake-model tests.
- Known issues: active CUDA call cannot be interrupted; normal shutdown completes current page before exiting; cleanup of rendered pages removes restart shortcut images but never completed text outputs; upstream model warnings remain non-fatal.
- Acceptance criteria: all 46 Phase 4 criteria passed. “1220 pages” was interpreted as the stated 12–20-page soak range; 12 pages were used, consistent with `PDF_MAX_PAGES=100`.
- Next allowed phase: Phase 5 frontend usability and packaging only; not started.
# Phase 5 — Frontend usability and Windows local packaging

Status: COMPLETED

Scope: production local launcher, job routes, system and maintenance views, result downloads, frontend smoke checks, offline packaged verification, and Windows scripts.

Files created: `scripts/preflight.ps1`, `scripts/setup-windows.ps1`, `scripts/start-local.ps1`, `scripts/stop-local.ps1`, `scripts/status-local.ps1`, `scripts/verify_phase5_local_app.ps1`, `docs/user-guide.md`, `docs/release-checklist.md`, `RELEASE.md`, and the dependency-free frontend smoke test.

Files modified: frontend routes/components/API client, job download API, configuration validation, runtime PID handling, README, setup/troubleshooting documentation, and `.gitignore`.

Spawn diagnosis: direct async and sync `node:child_process` probes passed. Standalone TypeScript passed. The earlier `spawn EPERM` was not reproducible after running from `apps/web` with clean generated output; no source or dependency workaround was required. The initial probe command was also affected by PowerShell backtick quoting.

Versions: Node 22.17.1, pnpm 10.13.1, Next.js 16.1.6, TypeScript 5.9.3.

Builds: default Turbopack build passed in 4.22 s and `next build --webpack` passed in 10.52 s. Both produced `.next/BUILD_ID`. The reliable documented command is `Set-Location apps\\web; pnpm exec next build`; invoking it through the root recursive `pnpm --filter web build` path reproduced `spawn EPERM` in this shell. Setup now invokes the workspace command directly.

Automated tests: backend 56 passed in 8.31 s; frontend 3 smoke checks passed; standalone `tsc --noEmit` passed.

Packaged verification: production startup returned backend and frontend readiness; one real image and one real three-page PDF completed offline; Markdown, TXT, and JSON downloads, frontend availability, and integrity endpoint passed. The verifier stopped both services.

Shutdown/restart: repeated stop was safe; a fresh production start returned worker `IDLE`, model `NOT_LOADED`, offline mode enabled, and valid localhost frontend/backend responses. Listener PID tracking was verified.

Known limitations: active CUDA inference remains cooperative; polling is used; frontend smoke tests are dependency-free source-contract tests; the transient `spawn EPERM` remains documented as an environment/command invocation issue, not a reproducible application failure.

Acceptance criteria: initial build gate and packaged backend/offline flow passed; browser verification was pending at that checkpoint. Superseded by the completion section below.

## Phase 5 verification continuation — 2026-07-12

- Stopped baseline: backend/frontend stopped, ports 8000/3000 free, no PID files.
- Preflight: all checks passed, including Python, Node, pnpm, backend/frontend dependencies, production `BUILD_ID`, CUDA/GPU, offline model files, database, write access, free disk, and ports.
- Setup: existing-installation idempotency passed; exit 0; `.env` SHA-256 unchanged; database and model preserved; no model download requested. This was not a fresh-machine test.
- Startup timing: total 4,386 ms; backend ready 4,165 ms; frontend ready 4,195 ms. Listener PIDs were recorded and status showed worker `IDLE`, model `NOT_LOADED`, offline mode enabled.
- Duplicate startup: second invocation exited 1 with a clear existing-backend message; no duplicate listeners.
- Shutdown: 1,285 ms; ports released; repeated stop exited 0.
- Stale PID: fake nonexistent PIDs were reported stale, removed/replaced, and startup succeeded without affecting unrelated processes.
- Packaged verifier: passed again; image job `13d1d881-fc0b-4b8a-a2e8-1348b002cdc5`, PDF job `9527effe-3e51-4df9-91fd-2c471473865d`, downloads and integrity verified, services stopped.
- Browser: in-app browser target unavailable (`browsers.list() = []`); no alternate browser backend was used. Browser route/action verification therefore remains the blocking criterion.

## Phase 5 browser completion — 2026-07-12

- Playwright: `@playwright/test` 1.61.1 added only to `apps/web`; Chromium 149.0.7827.55 installed via Playwright. Lockfile updated. No OCR/runtime dependency changed.
- Fixtures: generated non-sensitive `apps/web/e2e/fixtures/sample-image.png` and `sample-three-page.pdf`.
- Browser tests: 4 passed in 10.9 seconds using one Chromium worker against production startup. Routes `/`, `/jobs`, `/system`, `/maintenance` rendered. Image and PDF flows completed; PDF DPI 200 appeared conditionally; page summaries/lazy result, previews, downloads, integrity, and maintenance preview passed. Requests were restricted to `127.0.0.1:3000` and `127.0.0.1:8000`.
- Final regressions: frontend smoke 3 passed; TypeScript passed; backend 56 passed in 8.11 seconds; direct production build passed with `BUILD_ID` present; packaged verifier passed again.
- Startup/shutdown: packaged startup readiness approximately 4.3 seconds (backend 4.009 seconds, frontend 4.048 seconds); previous measured idle shutdown 1.285 seconds; repeated stop safe. Final process state stopped.
- Browser runner required `NODE_OPTIONS=--trace-uncaught` in this Windows/Codex execution environment to avoid transient runner `spawn EPERM`; this is a test-runner environment workaround, not an OCR/runtime dependency change.
- Acceptance criteria: all Phase 5 criteria passed. Phase 6 not started.

## Phase 6 — OCR quality evaluation and release decision

- Status: BLOCKED
- Dataset: 20 generated non-sensitive primary documents, two per category, with manifest and ground truth.
- Evidence: 100% completion/page success/integrity for primary jobs, but median CER 34.86%, median WER 54.55%, numeric accuracy 91.30%.
- Scope deviation: DPI selection used 12 documents rather than exactly six, producing 44 total jobs and exceeding the 38-job maximum. Raw results retained in `evaluation/reports/`.
- Release decision: REMAIN_RC. Phase 7 not started.

## Phase 6 remediation — 2026-07-12

- Status: BLOCKED
- Initial reports moved to `evaluation/reports/initial-invalid-run/`; raw outputs remain preserved.
- Canonical dataset constructed without new OCR: 38 records (20 primary + 18 six-document DPI records); 12 historical extra DPI records are labeled excluded.
- Scorer smoke tests: 4 passed. Remediation is incomplete: page-aligned multi-page scoring, explicit numeric-field manifest/schema, table-cell metrics, the required scorer edge-case suite, and factual eight-document manual layout review were not completed.
- No second OCR/evaluation iteration started. Release remains `REMAIN_RC`; Phase 7 not started.

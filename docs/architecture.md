# Architecture

Phase 2 uses FastAPI lifespan management to initialize SQLite, recover interrupted jobs, and start exactly one OCR worker. SQLite is the source of truth; an in-memory event only wakes the polling worker. A queued job is claimed inside a SQLite `BEGIN IMMEDIATE` transaction with a conditional update, preventing ordinary duplicate claims.

The model service starts as `NOT_LOADED`, loads the local snapshot lazily on the worker thread, moves through `LOADING` to `READY`, and remains resident for later jobs. GPU inference runs through `asyncio.to_thread()` under a single lock, keeping the API event loop responsive and limiting CUDA inference to one image at a time.

Uploads and outputs use generated UUID directories. Result Markdown, TXT, and JSON files are written through temporary files followed by atomic replacement. Phase 2 accepts images only; PDF rendering remains Phase 3 scope.

On startup, jobs left in `LOADING_MODEL`, `PROCESSING`, or `CANCEL_REQUESTED` are marked interrupted. Non-cancelled jobs with an existing source are requeued; a missing source becomes `FAILED/SOURCE_FILE_MISSING`. Because Phase 2 has one image per job, recovery reruns that image.

Phase 3 adds an idempotent schema-version 3 migration and `ocr_pages`. Existing Phase 2 image records are preserved; completed images are backfilled only with derivable one-page progress. A PDF upload creates one `PENDING` row per page. The worker opens the source PDF only to render the requested page, closes it, OCRs that rendered PNG, persists page outputs, recalculates counters from database states, and proceeds in ascending order. It never holds all pages in memory or runs page inference concurrently.

Page images remain under `data/pages/{job_id}` for debugging. Page Markdown/TXT live under `data/outputs/{job_id}/pages`; combined Markdown/TXT/JSON are regenerated atomically in page order. Failed pages receive explicit placeholders and do not erase completed pages.

Cancellation is cooperative. A queued job cancels before inference. Active page inference cannot be terminated safely; it finishes and persists that page, then the job stops before the next page. Restart recovery preserves completed pages, resets active pages to `RENDERED` when their image remains available or `PENDING` otherwise, and resumes only unfinished pages.

Phase 4 adds an independent asynchronous worker heartbeat. It updates while GPU inference executes in a worker thread, so long CUDA calls do not look stale. The lightweight worker endpoint exposes state, queue depth, active job/page, process RAM, and CUDA allocation without loading the model or result files.

SQLite connections use WAL, foreign keys, and a bounded busy timeout. Transactions are short: job claims/persistence happen before or after render/inference, never around them. Admission uses a `BEGIN IMMEDIATE` capacity check and insert. Storage status is cached for ten seconds; manual cleanup and orphan scans remain explicit operations.

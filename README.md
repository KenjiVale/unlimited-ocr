# Unlimited OCR Local

Local Windows OCR for images and multi-page PDFs using the official `baidu/Unlimited-OCR` model. The application runs a FastAPI backend, a single persistent CUDA worker, SQLite/local filesystem persistence, and a Next.js production frontend. OCR inference stays on the local machine.

Release: **Local OCR v0.1.0 — RELEASE_WITH_LIMITATIONS**

The release was evaluated on Windows 11 with an NVIDIA GeForce RTX 5070 (12,226 MiB), Python 3.12, Node.js 22.17.1, pnpm 10.13.1, PyTorch 2.8.0+cu129, torchvision 0.23.0+cu129, and Transformers 4.57.1. The evaluation used 38 bounded, generated, non-sensitive records. It is not a general OCR industry benchmark.

Known limitations:

- Low-resolution documents are **WEAK** and require manual verification.
- Table content and row order are evaluated, but visual table alignment may differ.
- CUDA cancellation is cooperative; an active inference call may finish before cancellation takes effect.
- One GPU inference runs at a time. Polling is used; SSE and WebSockets are not required.

## What is supported

| Input | Details |
| --- | --- |
| PNG, JPG, JPEG, WEBP | Single-image OCR. |
| PDF | Sequential page rendering and OCR; allowed DPI values are 150, 200, and 300. Default is 200. |
| Results | Markdown, plain TXT, and JSON metadata/content. |

Supported within the bounded evaluation: clean digital, scanned print, invoices/receipts, bilingual text, numeric-heavy documents, and multi-page PDFs. Tables and rotated documents are supported with limitations. Low-resolution input is weak.

## Technology

- Frontend: Next.js 16.1.6, React 19.2.3, TypeScript 5.9.3, Tailwind CSS.
- Backend: FastAPI 0.116.1 with Uvicorn.
- OCR: official `baidu/Unlimited-OCR`, Gundam mode, local Transformers/PyTorch CUDA runtime.
- Worker: one persistent GPU worker with SQLite-backed queue, heartbeat, recovery, retry, cancellation, and cleanup controls.
- Persistence: SQLite with WAL and local filesystem artifacts.
- PDF rendering: PyMuPDF 1.27.2.2.
- Tests: pytest, dependency-free frontend smoke tests, and Playwright Chromium E2E tests.
- Runtime: Windows PowerShell, localhost-only production startup.

## Requirements

### Minimum supported environment

These are the verified platform constraints, not a complete hardware benchmark:

- Windows 11.
- Python 3.12 (`>=3.12,<3.13`).
- Node.js LTS; the verified release used Node.js 22.17.1.
- pnpm; the verified release used pnpm 10.13.1.
- NVIDIA driver and CUDA-capable PyTorch installation.
- Local model snapshot with enough disk space for model files and OCR artifacts.

The exact minimum GPU VRAM and system RAM have not been formally benchmarked. The verified GPU has 12,226 MiB VRAM; Phase 6 peak allocation was 9,065 MiB and Phase 4 peak process RSS was 7,359,299,584 bytes. A 12 GB NVIDIA GPU and at least 16 GB system RAM are practical recommendations for this release, not hard compatibility guarantees.

Disk admission defaults to 5 GB free (`MIN_FREE_DISK_GB=5`). Keep additional space for model files, uploads, rendered PDF pages, logs, and outputs.

Use a current Chromium-based browser or Edge to access the local Next.js interface. Playwright Chromium is for project verification only and is not required for normal OCR use.

## Installation from a fresh clone

Open a normal PowerShell window, do not run as Administrator by default, and place the repository in a normal developer directory.

```powershell
Set-Location D:\Projects
git clone <repository-url> unlimited-ocr
Set-Location .\unlimited-ocr

# If script execution is blocked, scope this only to the current process:
Set-ExecutionPolicy -Scope Process Bypass

.\scripts\setup-windows.ps1
```

`setup-windows.ps1` creates or reuses `.venv`, installs the pinned backend extras, installs frontend dependencies with pnpm, creates required data/runtime directories, initializes SQLite, and builds the production frontend. It copies `.env.example` to `.env` only when `.env` does not exist. It does not overwrite an existing environment file.

The setup script does not download the large model unless explicitly requested:

```powershell
.\scripts\setup-windows.ps1 -DownloadModel
.\scripts\setup-windows.ps1 -DownloadModel -RunTests
```

If Node.js or pnpm is missing, install Node.js LTS and enable/install pnpm with the existing Windows package-management approach, then rerun setup. The setup script does not require Administrator privileges and does not change the global execution policy.

## Environment and offline mode

Copying `.env.example` is normally handled by setup. Important defaults are:

```env
API_HOST=127.0.0.1
API_PORT=8000
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
OCR_MODEL_ID=baidu/Unlimited-OCR
OCR_MODEL_PATH=./data/models/Unlimited-OCR
OCR_DEVICE=cuda
OCR_DTYPE=bfloat16
OCR_DEFAULT_MODE=gundam
OCR_CONCURRENCY=1
PDF_DEFAULT_DPI=200
PDF_MAX_PAGES=100
UPLOAD_MAX_MB=200
MAX_QUEUED_JOBS=50
MIN_FREE_DISK_GB=5
DATABASE_BUSY_TIMEOUT_MS=5000
DATABASE_JOURNAL_MODE=WAL
CLEANUP_ENABLED=false
```

After the complete model snapshot is available locally, set:

```env
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
```

Offline mode means this application restricts model loading to local files and does not use an external OCR API. It does not prove that every other process on the computer has no network access. There is no YouTube or cloud-service dependency in the OCR runtime.

## Start, stop, restart, and status

Use the production launcher; do not use `next dev` for normal operation:

```powershell
Set-Location D:\Projects\unlimited-ocr
.\scripts\preflight.ps1
.\scripts\start-local.ps1
```

The default URLs are:

- Frontend: <http://127.0.0.1:3000>
- Backend health: <http://127.0.0.1:8000/api/health>
- Backend API docs: <http://127.0.0.1:8000/docs>

Useful lifecycle commands:

```powershell
.\scripts\status-local.ps1
.\scripts\stop-local.ps1
.\scripts\start-local.ps1 -NoBrowser
.\scripts\stop-local.ps1   # safe to repeat
```

The launcher binds to `127.0.0.1`, waits for backend/frontend readiness, records actual listener PIDs under `.runtime`, and starts the built Next.js application. `stop-local.ps1` validates process ownership and waits for ports 8000 and 3000 to close. Never use broad commands such as `taskkill /IM python.exe` or `Stop-Process -Name node`.

## Using the browser application

1. Open `http://127.0.0.1:3000`.
2. On **OCR**, choose or drag a PNG/JPG/JPEG/WEBP image or PDF.
3. Select Gundam mode. For PDFs, choose 150, 200, or 300 DPI; 200 is the balanced default.
4. Submit the job. The interface shows queue state, worker state, page totals, processed/successful/failed pages, progress, current page, and errors.
5. Open **Jobs** for history, newest-first job records, status filters, retry, delete, and integrity actions.
6. Open a job for overview data, PDF page summaries, per-page results, Markdown/TXT/JSON previews, and downloads.
7. Cancellation is cooperative. A running CUDA page may finish before the job becomes cancelled.
8. Retry a failed page where supported, or retry an eligible job. Successful pages are preserved.
9. Run an integrity check for terminal jobs to validate persisted artifacts; it does not judge OCR meaning.
10. Use **System** for backend, GPU, model, worker, queue, storage, disk, and offline status.
11. Use **Maintenance** to preview cleanup. Cleanup is not automatic; rendered page images are the default target while source files and combined outputs remain protected by default.

## Results and storage

The application produces:

- Markdown: combined `result.md` and page Markdown files.
- TXT: combined `result.txt` and page text files.
- JSON: combined metadata/content `result.json`, including job/page status and errors.

Typical storage layout:

```text
data/
  app.db
  models/Unlimited-OCR/
  uploads/{job_id}/source.*
  pages/{job_id}/page_0001.png
  outputs/{job_id}/result.md
  outputs/{job_id}/result.txt
  outputs/{job_id}/result.json
  outputs/{job_id}/pages/page_0001.md
  outputs/{job_id}/pages/page_0001.txt
```

Runtime files and logs are kept separately:

```text
.runtime/
  backend.pid
  frontend.pid
  backend.process.json
  frontend.process.json
  backend.log
  backend.err.log
  frontend.log
  frontend.err.log
  startup.timings.json
```

Do not delete `data/app.db`, `data/models`, uploads, or outputs to solve ordinary startup problems. SQLite migrations are designed to preserve existing image and PDF jobs.

## API examples

The browser is the recommended interface. The backend remains available at `http://127.0.0.1:8000` for local automation. Existing job APIs include:

```text
GET    /api/health
GET    /api/system/gpu
GET    /api/system/model
GET    /api/system/worker
GET    /api/system/storage
POST   /api/ocr/jobs
GET    /api/ocr/jobs
GET    /api/ocr/jobs/{id}
GET    /api/ocr/jobs/{id}/pages
GET    /api/ocr/jobs/{id}/result
GET    /api/ocr/jobs/{id}/pages/{page}/result
GET    /api/ocr/jobs/{id}/download/markdown
GET    /api/ocr/jobs/{id}/download/text
GET    /api/ocr/jobs/{id}/download/json
POST   /api/ocr/jobs/{id}/cancel
POST   /api/ocr/jobs/{id}/retry
DELETE /api/ocr/jobs/{id}
GET    /api/ocr/jobs/{id}/integrity
POST   /api/maintenance/cleanup/preview
POST   /api/maintenance/cleanup/run
```

Example PDF upload with Windows `curl.exe`:

```powershell
$job = curl.exe -s -X POST http://127.0.0.1:8000/api/ocr/jobs `
  -F "file=@C:\path\document.pdf;type=application/pdf" `
  -F "ocr_mode=gundam" `
  -F "pdf_dpi=200" | ConvertFrom-Json

Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($job.id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($job.id)/pages"
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($job.id)/result"
```

## Testing and verification

Run the backend tests with the repository virtual environment:

```powershell
Set-Location D:\Projects\unlimited-ocr\services\api
..\..\.venv\Scripts\python.exe -m pytest
..\..\.venv\Scripts\python.exe -m pytest tests\test_phase6_scorer.py -v
```

Run frontend checks and the supported direct production build:

```powershell
Set-Location D:\Projects\unlimited-ocr\apps\web
pnpm test
pnpm exec tsc --noEmit
pnpm exec next build
Test-Path .next\BUILD_ID
```

The verified release build is the direct workspace command above. Do not use the unreliable root recursive `pnpm --filter web build` command as the release gate.

Run Playwright only against the production application:

```powershell
Set-Location D:\Projects\unlimited-ocr
.\scripts\start-local.ps1 -NoBrowser
Set-Location apps\web
pnpm exec playwright install chromium   # first verification setup only
pnpm exec playwright test
Set-Location ..\..
.\scripts\stop-local.ps1
```

Run the packaged local verifier from the repository root:

```powershell
Set-Location D:\Projects\unlimited-ocr
.\scripts\verify_phase5_local_app.ps1
```

The verifier checks production startup, offline image/PDF OCR, downloads, integrity, frontend access, and cleanup. For the final lifecycle gate, use a normal non-administrator PowerShell session and require two exit-code-zero runs with both ports free afterward.

## Troubleshooting

### CUDA unavailable or model loading fails

```powershell
nvidia-smi
.\.venv\Scripts\python.exe scripts\check_cuda.py
```

Confirm the verified CUDA-enabled PyTorch pair (`torch 2.8.0+cu129`, `torchvision 0.23.0+cu129`) and that `data\models\Unlimited-OCR\config.json` plus model weights exist. If offline model files are missing, temporarily run `scripts\setup-windows.ps1 -DownloadModel` while online. Do not delete the model cache or change dependencies without evidence.

### Ports are occupied

```powershell
.\scripts\status-local.ps1
Get-NetTCPConnection -State Listen -LocalPort 8000,3000
```

Use `scripts\stop-local.ps1` only for validated project processes. An unrelated port owner must not be killed; choose free ports or stop that unrelated application yourself.

### Stale PID or metadata files

Run `status-local.ps1`, then `stop-local.ps1`. The lifecycle layer validates command lines and port ownership, recovers a validated project listener when PID files are missing, and removes proven stale metadata. Never substitute a broad process kill.

### Frontend build problems

Stop project processes and remove only generated `apps\web\.next` artifacts. Then run:

```powershell
Set-Location apps\web
pnpm exec tsc --noEmit
pnpm exec next build
```

Do not disable TypeScript checking, fabricate `BUILD_ID`, use `next dev` as the packaged runtime, or use the unreliable root recursive build command.

### Offline operation

Offline operation requires a complete local model snapshot and these settings:

```env
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
```

The application does not use cloud OCR, YouTube, or an external inference API. Initial dependency/model installation may require network access; inference after the snapshot is present is local.

### Low-resolution OCR quality

Low-resolution input is weak in the bounded evaluation. Review Markdown/TXT/JSON results and important numbers manually. The release does not silently correct OCR with an LLM or a second model.

### Disk, queue, PDF, and database errors

- `INSUFFICIENT_DISK_SPACE`: free disk or adjust the deliberate 5 GB safety threshold.
- `QUEUE_CAPACITY_REACHED`: wait for queued jobs; the default is 50.
- `PDF_PASSWORD_REQUIRED`: encrypted/password-protected PDFs are rejected; password submission is not implemented.
- `PDF_PAGE_LIMIT_EXCEEDED`: the default maximum is 100 pages.
- `DATABASE_BUSY`: SQLite WAL/busy-timeout protection rejected a write; completed output files are not silently duplicated.
- `RESULT_NOT_AVAILABLE`: wait for a terminal job/page state.

## Security and privacy

- Bindings default to localhost (`127.0.0.1`), not `0.0.0.0`.
- Uploaded documents and OCR results remain on the configured local filesystem.
- Model inference runs through the local CUDA runtime after model files are downloaded.
- No authentication or multi-user isolation is provided; do not expose this service publicly.
- Do not commit `.env`, private documents, model files, or generated OCR outputs.
- Cleanup is manual and intentionally conservative. Preview before deleting rendered pages.

## Release information

**Local OCR v0.1.0 — RELEASE_WITH_LIMITATIONS** is the verified local Windows release. The release has passed the bounded backend/frontend/browser/offline checks and lifecycle verification. Use it routinely for the documented supported categories, and manually verify low-resolution documents and visually sensitive tables. Phase 7 has not started.

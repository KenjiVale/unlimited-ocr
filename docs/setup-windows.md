# Windows setup

## Prerequisites

Install a current NVIDIA driver compatible with the PyTorch CUDA build, Python 3.12 (enable long-path support), Node.js LTS, and pnpm. The official model card reports testing with Python 3.12.3, PyTorch 2.10.0/CUDA 12.9, torchvision 0.25.0, and Transformers 4.57.1. At verification time the official CUDA 12.9 wheel index did not publish that pair; this project therefore pins the latest complete pair available there, PyTorch 2.8.0 and torchvision 0.23.0, pending real-model compatibility verification.

## Backend (PowerShell)

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".\services\api[test]"
# Install the CUDA wheel from the current command at https://pytorch.org/get-started/locally/
pip install torch==2.8.0+cu129 torchvision==0.23.0+cu129 --index-url https://download.pytorch.org/whl/cu129
pip install -e ".\services\api[ocr]"
Copy-Item .env.example .env
python scripts\check_cuda.py
python scripts\download_model.py
uvicorn app.main:app --app-dir services\api --host 127.0.0.1 --port 8000
```

Do not use `--host 0.0.0.0`. If activation is blocked, use the execution-policy command above or call `.venv\Scripts\python.exe` directly. Enable Windows long paths through Group Policy or `LongPathsEnabled` if model snapshot paths fail.

## Phase 5 production local app

Run the bounded setup and preflight scripts. They do not overwrite an existing `.env` and model download requires `-DownloadModel` explicitly:

```powershell
.\scripts\setup-windows.ps1 -RunTests
.\scripts\preflight.ps1
.\scripts\start-local.ps1
.\scripts\status-local.ps1
.\scripts\stop-local.ps1
```

The production build is `pnpm exec next build` from `apps\web`; `next start` serves the resulting build on `127.0.0.1:3000`. The verified Windows environment uses Next.js 16.1.6, Node 22.17.1, pnpm 10.13.1, and TypeScript 5.9.3. `scripts\verify_phase5_local_app.ps1` runs offline image/PDF, downloads, integrity, and stop verification.

For development-only browser verification:

```powershell
Set-Location apps\web
pnpm exec playwright install chromium
pnpm exec playwright test
```

Playwright and Chromium are not required for normal local OCR operation.

## Frontend development

```powershell
corepack enable
pnpm install
pnpm dev:web
```

## Real image smoke test

```powershell
python scripts\smoke_test_image.py C:\path\to\sample.png
```

## Offline runtime

After downloading the complete snapshot, set these values in `.env`:

```env
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
```

The smoke test loads `data/models/Unlimited-OCR` with `local_files_only=True` unless `--online` is explicitly passed. Disconnect networking and rerun it to verify offline operation.

## Phase 2 image-job API

Start the backend from the repository root after activating the virtual environment:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
python -m uvicorn app.main:app --app-dir services\api --host 127.0.0.1 --port 8000
```

Create a job with Windows `curl.exe` and retain its ID:

```powershell
$job = curl.exe -s -X POST http://127.0.0.1:8000/api/ocr/jobs `
  -F "file=@C:\path\document.png;type=image/png" `
  -F "ocr_mode=gundam" | ConvertFrom-Json
$job.id
```

Check status and retrieve results:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($job.id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($job.id)/result"
```

Cancel or retry:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/ocr/jobs/$($job.id)/cancel"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/ocr/jobs/$($job.id)/retry"
```

Queued cancellation is immediate. Cancellation during active CUDA inference completes the current image safely, preserves generated result files, and then marks the job `CANCELLED`.

## PDF jobs

Upload an unencrypted PDF at the balanced 200 DPI default:

```powershell
$pdfJob = curl.exe -s -X POST http://127.0.0.1:8000/api/ocr/jobs `
  -F "file=@C:\path\document.pdf;type=application/pdf" `
  -F "ocr_mode=gundam" `
  -F "pdf_dpi=200" | ConvertFrom-Json
```

Poll progress and list page states:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)/pages"
```

Fetch an individual page or combined result:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)/pages/1/result"
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)/result"
```

Cancel, retry one failed page, retry unfinished PDF pages, or delete a non-active job:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)/cancel"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)/pages/2/retry"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)/retry"
Invoke-RestMethod -Method Delete "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)"
```

The schema-version 3 migration runs idempotently at startup and preserves existing Phase 2 image jobs. Do not delete `data\app.db` during upgrades.

## Phase 4 operations

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/system/worker
Invoke-RestMethod http://127.0.0.1:8000/api/system/storage
Invoke-RestMethod "http://127.0.0.1:8000/api/ocr/jobs/$($pdfJob.id)/integrity"
```

Preview before deleting rendered pages. Source and combined outputs stay excluded unless explicitly requested:

```powershell
$cleanup = @{ older_than_days = 30; include_rendered_pages = $true; include_source_files = $false; include_outputs = $false } | ConvertTo-Json
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/maintenance/cleanup/preview -ContentType application/json -Body $cleanup
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/maintenance/cleanup/run -ContentType application/json -Body $cleanup
```

Operational verifiers require a running offline backend:

```powershell
python scripts\verify_phase4_soak.py --pages 12
python scripts\verify_phase4_queue.py
python scripts\verify_phase4_restart.py
```

Reliability settings use a 500 ms worker poll, 5-second heartbeat, 120-second stale threshold, 5 GB disk threshold, 50 queued jobs, WAL SQLite, 5-second busy timeout, and 30-second shutdown grace by default. Automatic cleanup is disabled.

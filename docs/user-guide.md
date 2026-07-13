# Local OCR user guide

All OCR runs on this computer and local CUDA GPU. When System reports offline mode, model loading is restricted to the downloaded local snapshot.

```powershell
.\scripts\preflight.ps1
.\scripts\start-local.ps1
.\scripts\status-local.ps1
.\scripts\stop-local.ps1
```

Open `http://127.0.0.1:3000`. Upload PNG, JPG, JPEG, WEBP, or PDF. PDFs offer 150, 200, and 300 DPI; 200 is the normal balanced choice. Jobs are processed one at a time. Cancellation is cooperative: an active CUDA page can finish before the worker stops.

Use Jobs for history, per-page state, retry, delete, integrity, previews, and downloads. Use Maintenance to preview cleanup before running it. Rendered pages are selected by default; sources and results are not. Removing rendered pages preserves OCR results, but recovery may render unfinished pages again.

Browser E2E tooling is for project verification only and is not needed to run OCR.

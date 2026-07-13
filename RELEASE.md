# Local OCR v0.1.0

Release date: 2026-07-12. Windows 11 local release with limitations, not a general production claim. Status: Phase 6 COMPLETED.

- Verified GPU: NVIDIA GeForce RTX 5070 (12,226 MiB)
- Verified runtime: Python 3.12, PyTorch 2.8.0+cu129, torchvision 0.23.0+cu129, Transformers 4.57.1
- Model: `baidu/Unlimited-OCR`, local snapshot, Gundam mode
- Inputs: PNG, JPG, JPEG, WEBP, PDF
- Setup: `./scripts/setup-windows.ps1`
- Start: `./scripts/start-local.ps1`
- Stop: `./scripts/stop-local.ps1`
- Status: `./scripts/status-local.ps1`

Known limits: one GPU job at a time; active CUDA inference cannot be interrupted immediately; polling only; rendered pages are retained until explicit cleanup; low-resolution documents require human verification; table scoring does not assess visual alignment.

Verification: 83 scorer tests, 139 backend tests, frontend smoke 3 passed, Playwright Chromium 4 passed against production startup, TypeScript, direct workspace production build, BUILD_ID, and two external normal-PowerShell packaged verifier runs passed. Low-resolution category relaxed CER is 22.45% and remains explicitly weak. Supported production build is `Set-Location apps\web; pnpm exec next build`.

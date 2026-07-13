# Local release checklist

- Run `scripts\preflight.ps1`.
- Run backend tests and `Set-Location apps\web; pnpm exec next build`.
- Start with `scripts\start-local.ps1 -NoBrowser`.
- Confirm `/api/health`, the frontend, System status, and offline model status.
- Complete one image and one three-page PDF locally.
- Check integrity and all three result downloads.
- Preview rendered-page cleanup; only execute after explicit confirmation.
- Stop twice with `scripts\stop-local.ps1`; confirm the second invocation is safe.
- Complete real-browser verification of `/`, `/jobs`, `/jobs/{id}`, `/system`, and `/maintenance` before marking the release candidate complete. The in-app browser was unavailable during the 2026-07-12 verification.
# Phase 6 release decision

- Lifecycle correction: **COMPLETED**; two external normal-PowerShell verifier runs exited 0 with clean ports and no PID/metadata/process remnants.
- Final decision: **RELEASE_WITH_LIMITATIONS** — Local OCR v0.1.0.

- Canonical evaluation: 38 records; historical physical jobs: 44, with 12 extra historical DPI records excluded from the decision dataset.
- Screenshot-backed manual review: 8/8 required documents.
- Final decision: **REMAIN_RC** — Local OCR v0.1.0-rc1; packaged verifier child-process/PID cleanup must be corrected and reverified.
- Limitation: low-resolution fixture category median relaxed CER was 22.45% and exceeds the 15% category threshold.
- Regression evidence: 83 scorer tests, 139 backend tests, 3 frontend smoke checks, 4 Playwright tests, TypeScript, and BUILD_ID passed.

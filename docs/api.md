# API (Phase 2)

- `GET /api/health`: process liveness; never loads PyTorch or the OCR model.
- `GET /api/system/gpu`: CUDA availability, device, VRAM, and PyTorch versions.
- `GET /api/system/model`: lazy model state and load metadata.
- `POST /api/ocr/jobs`: multipart image/PDF upload (`file`, `ocr_mode=gundam`, `pdf_dpi`), returns `202`.
- `GET /api/ocr/jobs`: list with `limit`, `offset`, and optional `status`.
- `GET /api/ocr/jobs/{id}`: persisted job metadata.
- `GET /api/ocr/jobs/{id}/result`: completed Markdown/TXT result and metrics.
- `POST /api/ocr/jobs/{id}/cancel`: cooperative cancellation.
- `POST /api/ocr/jobs/{id}/retry`: retry `FAILED`, `INTERRUPTED`, or `CANCELLED`.
- `DELETE /api/ocr/jobs/{id}`: delete non-active job database/storage data.
- `GET /api/ocr/jobs/{id}/pages`: ordered page summaries without OCR text.
- `GET /api/ocr/jobs/{id}/pages/{number}`: page metadata.
- `GET /api/ocr/jobs/{id}/pages/{number}/result`: completed page Markdown/TXT.
- `POST /api/ocr/jobs/{id}/pages/{number}/retry`: requeue one failed/skipped page while preserving successful pages.
- `GET /api/system/worker`: heartbeat, state, active job/page, queue depth, process RAM, and current CUDA allocation.
- `GET /api/system/storage`: cached free/used disk, storage sizes, orphan count, and admission status.
- `GET /api/ocr/jobs/{id}/integrity`: validates artifacts without returning OCR text.
- `POST /api/maintenance/cleanup/preview`: safe cleanup plan.
- `POST /api/maintenance/cleanup/run`: explicit cleanup execution; rendered pages only by default request body.

Errors use `{"error":{"code":"...","message":"...","details":null}}`. Supported inputs are PNG, JPEG, WebP, and unencrypted PDF. PDF DPI is restricted to 150, 200, or 300.

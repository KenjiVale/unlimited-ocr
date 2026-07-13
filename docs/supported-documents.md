# Supported document guidance

The local application is operationally stable for clean, single-column, high-resolution documents. Use 200 DPI for normal PDFs. Avoid relying on it for exact financial/numeric extraction, complex tables, multi-column order, low-resolution scans, or rotated inputs without human review.

The current release is suitable for the documented supported categories. Low-resolution documents remain weak and require human verification.

## Phase 6 bounded guidance

This is a bounded local evaluation using generated, non-sensitive fixtures. It is not a general industry OCR benchmark.

| Category | Guidance | Notes |
| --- | --- | --- |
| Clean digital | SUPPORTED | Exact content on the two primary fixtures. |
| Scanned print | SUPPORTED | Exact content on the two primary fixtures. |
| Low resolution | WEAK | Median relaxed CER 22.45%; verify results manually. |
| Rotated | SUPPORTED_WITH_LIMITATIONS | One primary fixture had a minor content error. |
| Multi-column | SUPPORTED_WITH_LIMITATIONS | Fixtures render as single-column labelled text; real visual columns were not evaluated. |
| Tables | SUPPORTED_WITH_LIMITATIONS | Cell content and row order passed; visual alignment was not measured. |
| Invoice and receipt | SUPPORTED | Bounded identifiers, dates, and currency fields passed. |
| Bilingual | SUPPORTED | Exact content on the two primary fixtures. |
| Numeric-heavy | SUPPORTED | Bounded numeric fields passed. |
| Multi-page PDF | SUPPORTED | Page boundaries and page-number alignment passed. |

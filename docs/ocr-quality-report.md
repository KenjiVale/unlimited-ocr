# Phase 6 OCR quality report

Final decision: **RELEASE_WITH_LIMITATIONS** — Local OCR v0.1.0. Lifecycle correction completed with two external normal-PowerShell verifier runs exiting 0 and clean shutdown. Low-resolution documents remain weak and require manual verification. Tables preserve content and row order, but visual alignment may differ. This is a bounded synthetic-fixture evaluation, not a general OCR benchmark.

This is a bounded local evaluation on Windows 11 / RTX 5070 using Unlimited-OCR in Gundam mode.

- Primary corpus: 20 generated non-sensitive documents, two per required category.
- Primary results: 100% document completion, 100% page success, and 100% integrity pass rate.
- Scoring: NFC normalization, CRLF normalization, whitespace collapse, Levenshtein CER/WER. Raw model Markdown was not corrected.
- Primary median CER: 34.86%; median WER: 54.55%; numeric-field accuracy: 91.30%.
- Performance: maximum recorded primary duration 7,302 ms; maximum allocated VRAM 9,065 MiB.

## Final Phase 6 decision

The bounded local evaluation is complete: 38 canonical records (20 primary and 18 DPI records), with eight factual screenshot-backed layout reviews. The decision is **REMAIN_RC** as Local OCR v0.1.0-rc1. Low-resolution category median relaxed CER was 22.45%, above the unchanged 15% category threshold. The packaged verifier wrapper also did not return and left scoped listener children without PID files, so its final stop gate was not accepted. This is a bounded local evaluation using generated, non-sensitive fixtures, not an industry OCR benchmark.

The quality gates for routine release did not pass. Generated low-resolution, rotation, multi-column, table, and multi-page fixtures are useful for failure discovery but are not a formal industry benchmark.

Important scope deviation: the DPI runner selected two samples from each representative category, producing 44 jobs rather than the allowed 38. The raw evidence is retained, but Phase 6 cannot be marked complete from this run.

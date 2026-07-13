# Phase 6 final quality report

Lifecycle correction: **COMPLETED**. Two external normal-PowerShell verifier runs exited with code 0 and cleanup passed.

Decision: **RELEASE_WITH_LIMITATIONS** — Local OCR v0.1.0.

Decision: **REMAIN_RC** — Local OCR v0.1.0-rc1.

## Threshold results

| Metric | Actual | Required | Status |
| --- | ---: | --- | --- |
| Document completion rate | 1.0 | >= 0.95 | PASS |
| Page success rate | 1.0 | >= 0.98 | PASS |
| Integrity pass rate | 1.0 | = 1.0 | PASS |
| Median relaxed content CER | 0.0 | <= 0.05 | PASS |
| Median relaxed content WER | 0.0 | <= 0.10 | PASS |
| Numeric-field accuracy | 1.0 | >= 0.95 | PASS |
| No category median relaxed CER above 15% | 0.22448979591836735 | <= 0.15 | FAIL |
| Median overall layout score | 4.0 | >= 3 | PASS |
| Minimum table overall score | 3 | >= 2 | PASS |
| Minimum multi-column overall score | 4 | >= 2 | PASS |
| Median page inference duration | 2046 | <= 5000 ms | PASS |
| CUDA OOM | 0 | 0 | PASS |
| Application crashes | 0 | 0 | PASS |

## Limitations

- Low-resolution generated fixtures exceed the 15% category median relaxed-CER threshold (22.45%).
- Table cell scoring verifies content and row order, not visual alignment.
- This is a bounded local evaluation using generated, non-sensitive fixtures; it is not an industry OCR benchmark.

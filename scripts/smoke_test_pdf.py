from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the first PDF page and run the image smoke test.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--dpi", type=int, choices=(150, 200, 300), default=200)
    args, rest = parser.parse_known_args()
    try:
        import fitz
        if not args.pdf.is_file(): raise RuntimeError(f"File not found: {args.pdf}")
        with fitz.open(args.pdf) as doc:
            if doc.page_count < 1: raise RuntimeError("PDF has no pages")
            with tempfile.TemporaryDirectory(prefix="unlimited_ocr_smoke_") as temp:
                image = Path(temp) / "page_0001.png"
                doc[0].get_pixmap(matrix=fitz.Matrix(args.dpi / 72, args.dpi / 72)).save(image)
                script = Path(__file__).with_name("smoke_test_image.py")
                return subprocess.run([sys.executable, str(script), str(image), *rest], check=False).returncode
    except Exception as exc:
        print(f"PDF_SMOKE_TEST_FAILED: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    sys.exit(main())


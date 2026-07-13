from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FILES = {
    "config.json", "tokenizer.json", "tokenizer_config.json",
    "special_tokens_map.json", "processor_config.json",
    "modeling_unlimitedocr.py", "modeling_deepseekv2.py",
    "configuration_deepseek_v2.py", "conversation.py", "deepencoder.py",
}


def verify_model(path: Path) -> list[str]:
    missing = sorted(name for name in REQUIRED_FILES if not (path / name).is_file())
    weights = list(path.glob("*.safetensors"))
    if not weights:
        missing.append("*.safetensors")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the complete Unlimited-OCR snapshot.")
    parser.add_argument("--model-id", default="baidu/Unlimited-OCR")
    parser.add_argument("--output", type=Path, default=Path("data/models/Unlimited-OCR"))
    args = parser.parse_args()
    try:
        from huggingface_hub import snapshot_download
        args.output.mkdir(parents=True, exist_ok=True)
        snapshot_download(repo_id=args.model_id, local_dir=args.output)
        missing = verify_model(args.output)
        if missing:
            raise RuntimeError(f"Downloaded snapshot is incomplete; missing: {', '.join(missing)}")
        print(json.dumps({"status": "ok", "model_id": args.model_id, "path": str(args.output.resolve())}, indent=2))
        return 0
    except Exception as exc:
        print(f"MODEL_DOWNLOAD_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


from __future__ import annotations

import argparse
import gc
import os
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Unlimited-OCR inference on one local image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--model-path", type=Path, default=Path("data/models/Unlimited-OCR"))
    parser.add_argument("--output", type=Path, default=Path("data/outputs/smoke-image"))
    parser.add_argument("--mode", choices=("gundam", "base"), default="gundam")
    parser.add_argument("--max-length", type=int, default=8192)
    parser.add_argument("--online", action="store_true", help="Allow model ID fallback/network access.")
    args = parser.parse_args()
    cache_root = Path("data/.cache").resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_root / "huggingface"))
    os.environ.setdefault("HF_MODULES_CACHE", str(cache_root / "huggingface" / "modules"))
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    if not args.image.is_file():
        print(f"INVALID_IMAGE: File not found: {args.image}", file=sys.stderr); return 1
    try:
        from PIL import Image
        with Image.open(args.image) as image:
            image.verify()
        import torch
        from transformers import AutoModel, AutoTokenizer
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA_UNAVAILABLE: CUDA is not available.")
        source = str(args.model_path if args.model_path.is_dir() else "baidu/Unlimited-OCR")
        if source == "baidu/Unlimited-OCR" and not args.online:
            raise RuntimeError(f"OFFLINE_MODEL_NOT_AVAILABLE: {args.model_path}")
        local_only = not args.online
        args.output.mkdir(parents=True, exist_ok=True)
        torch.cuda.reset_peak_memory_stats()
        load_started = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=True, local_files_only=local_only)
        model = AutoModel.from_pretrained(source, trust_remote_code=True, use_safetensors=True, torch_dtype=torch.bfloat16, local_files_only=local_only)
        model = model.eval().cuda()
        load_seconds = time.perf_counter() - load_started
        image_size, crop_mode = (640, True) if args.mode == "gundam" else (1024, False)
        infer_started = time.perf_counter()
        with torch.inference_mode():
            result = model.infer(tokenizer, prompt="<image>document parsing.", image_file=str(args.image.resolve()), output_path=str(args.output.resolve()), base_size=1024, image_size=image_size, crop_mode=crop_mode, max_length=args.max_length, no_repeat_ngram_size=35, ngram_window=128, save_results=True)
        torch.cuda.synchronize()
        infer_seconds = time.perf_counter() - infer_started
        if isinstance(result, str):
            (args.output / "result.md").write_text(result, encoding="utf-8")
        print(f"model_load_seconds={load_seconds:.3f}")
        print(f"inference_seconds={infer_seconds:.3f}")
        print(f"peak_allocated_vram_mb={torch.cuda.max_memory_allocated() // (1024 * 1024)}")
        print(f"output_directory={args.output.resolve()}")
        return 0
    except Exception as exc:
        print(f"MODEL_INFERENCE_FAILED: {exc}", file=sys.stderr)
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available(): torch.cuda.empty_cache()
        except ImportError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())

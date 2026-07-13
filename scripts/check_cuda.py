from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        import torch
    except ImportError:
        print(json.dumps({"cuda_available": False, "error": "PyTorch is not installed."}, indent=2))
        return 1

    available = torch.cuda.is_available()
    result: dict[str, object] = {
        "cuda_available": available,
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "device_count": torch.cuda.device_count(),
    }
    if available:
        device = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(device)
        result.update(device_name=torch.cuda.get_device_name(device), total_vram_mb=props.total_memory // (1024 * 1024))
    else:
        result["error"] = "CUDA is not available. Install a CUDA-enabled PyTorch build and verify the NVIDIA driver."
    print(json.dumps(result, indent=2))
    return 0 if available else 1


if __name__ == "__main__":
    sys.exit(main())


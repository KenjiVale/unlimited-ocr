from __future__ import annotations

from app.schemas.system import GPUResponse


def get_gpu_status() -> GPUResponse:
    try:
        import torch
    except ImportError:
        return GPUResponse(
            cuda_available=False, device_name=None, device_count=0,
            total_vram_mb=0, allocated_vram_mb=0, reserved_vram_mb=0,
            torch_version=None, torch_cuda_version=None,
            error="PyTorch is not installed.",
        )

    if not torch.cuda.is_available():
        return GPUResponse(
            cuda_available=False, device_name=None, device_count=torch.cuda.device_count(),
            total_vram_mb=0, allocated_vram_mb=0, reserved_vram_mb=0,
            torch_version=torch.__version__, torch_cuda_version=torch.version.cuda,
            error="CUDA is not available.",
        )

    device = torch.cuda.current_device()
    properties = torch.cuda.get_device_properties(device)
    mib = 1024 * 1024
    return GPUResponse(
        cuda_available=True,
        device_name=torch.cuda.get_device_name(device),
        device_count=torch.cuda.device_count(),
        total_vram_mb=properties.total_memory // mib,
        allocated_vram_mb=torch.cuda.memory_allocated(device) // mib,
        reserved_vram_mb=torch.cuda.memory_reserved(device) // mib,
        torch_version=torch.__version__,
        torch_cuda_version=torch.version.cuda,
    )


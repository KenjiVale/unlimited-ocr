from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_env: str
    model_loaded: bool = False


class GPUResponse(BaseModel):
    cuda_available: bool
    device_name: str | None
    device_count: int
    total_vram_mb: int
    allocated_vram_mb: int
    reserved_vram_mb: int
    torch_version: str | None
    torch_cuda_version: str | None
    error: str | None = None


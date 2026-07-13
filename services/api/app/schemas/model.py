from datetime import datetime

from pydantic import BaseModel


class ModelStatusResponse(BaseModel):
    status: str
    model_id: str
    model_path: str
    device: str
    dtype: str
    offline_mode: bool
    loaded_at: datetime | None
    load_duration_ms: int | None
    last_error: str | None


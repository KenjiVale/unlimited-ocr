from fastapi import APIRouter, Request
from app.schemas.reliability import CleanupRequest, CleanupResponse

router=APIRouter(prefix="/api/maintenance",tags=["maintenance"])

@router.post("/cleanup/preview",response_model=CleanupResponse)
def preview(request:Request, body:CleanupRequest)->CleanupResponse:
    result,_=request.app.state.cleanup_service.plan(body); return CleanupResponse(**result)

@router.post("/cleanup/run",response_model=CleanupResponse)
def run(request:Request, body:CleanupRequest)->CleanupResponse:
    return CleanupResponse(**request.app.state.cleanup_service.run(body))

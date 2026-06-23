from fastapi import APIRouter, Depends, status

from app.auth import verify_web_token
from app.schemas import AnalyzeInterviewRequest, JobResponse
from app.services import jobs as job_service
from app.storage import get_storage_backend
from app.storage.protocol import StorageBackend

router = APIRouter(prefix="/v1", tags=["analyze"])


def get_storage() -> StorageBackend:
    return get_storage_backend()


@router.post("/analyze-interview", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_analyze_interview_job(
    body: AnalyzeInterviewRequest,
    _: None = Depends(verify_web_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    return await job_service.create_analyze_job(storage, body=body)

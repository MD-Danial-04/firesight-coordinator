from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.auth import verify_web_token
from app.schemas import AnalyzeInterviewRequest, AnalyzePhotoContext, JobResponse
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


@router.post("/analyze-photo", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_analyze_photo_job(
    file: UploadFile = File(...),
    location_of_fire: str | None = Form(default=None),
    incident_type_name: str | None = Form(default=None),
    stop_message_excerpt: str | None = Form(default=None),
    field_notes_excerpt: str | None = Form(default=None),
    _: None = Depends(verify_web_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    context = AnalyzePhotoContext(
        location_of_fire=location_of_fire,
        incident_type_name=incident_type_name,
        stop_message_excerpt=stop_message_excerpt,
        field_notes_excerpt=field_notes_excerpt,
    )
    filename = file.filename or "photo.jpg"
    return await job_service.create_photo_analyze_job(
        storage,
        image_bytes=image_bytes,
        filename=filename,
        context=context,
    )

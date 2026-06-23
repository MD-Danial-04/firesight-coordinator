import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.auth import verify_web_token
from app.schemas import ExtractJobRequest, JobResponse, MessageType
from app.services import jobs as job_service
from app.storage import get_storage_backend
from app.storage.protocol import StorageBackend

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


def get_storage() -> StorageBackend:
    return get_storage_backend()


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    file: UploadFile = File(...),
    message_type: MessageType = Form("stop_message"),
    incident_type_name: str | None = Form(None),
    _: None = Depends(verify_web_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio file is empty")
    filename = file.filename or "audio.webm"
    return await job_service.create_job(
        storage,
        audio_bytes=audio_bytes,
        filename=filename,
        message_type=message_type,
        incident_type_name=incident_type_name,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    _: None = Depends(verify_web_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    return await job_service.get_job(storage, job_id)


@router.post("/{job_id}/extract", response_model=JobResponse)
async def request_extraction(
    job_id: UUID,
    body: ExtractJobRequest,
    _: None = Depends(verify_web_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    return await job_service.request_extraction(
        storage,
        job_id,
        text=body.text,
        message_type=body.message_type,
        incident_type_name=body.incident_type_name,
    )


@router.get("/{job_id}/events")
async def job_events(
    job_id: UUID,
    _: None = Depends(verify_web_token),
    storage: StorageBackend = Depends(get_storage),
) -> StreamingResponse:
    job = await storage.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    async def event_stream():
        last_status: str | None = None
        for _ in range(300):
            current = await storage.get_job(job_id)
            if current is None:
                yield _format_sse({"event": "error", "detail": "Job not found"})
                break
            if current.status != last_status:
                payload = job_service.job_to_response(current).model_dump(mode="json")
                yield _format_sse({"event": "status", "job": payload})
                last_status = current.status
            if current.status in ("transcribed", "completed", "failed"):
                break
            await asyncio.sleep(1)
        yield _format_sse({"event": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

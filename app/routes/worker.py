from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.auth import verify_worker_token
from app.schemas import (
    JobResponse,
    WorkerAnalysisCompleteRequest,
    WorkerClaimResponse,
    WorkerExtractCompleteRequest,
    WorkerFailRequest,
    WorkerTranscribeRequest,
)
from app.services import jobs as job_service
from app.storage import get_storage_backend
from app.storage.protocol import StorageBackend

router = APIRouter(prefix="/v1/worker", tags=["worker"])


def get_storage() -> StorageBackend:
    return get_storage_backend()


@router.post("/claim", response_model=WorkerClaimResponse | None)
async def claim_job(
    _: None = Depends(verify_worker_token),
    storage: StorageBackend = Depends(get_storage),
) -> WorkerClaimResponse | None:
    return await job_service.claim_next_job(storage)


@router.get("/jobs/{job_id}/audio")
async def download_job_audio(
    job_id: UUID,
    _: None = Depends(verify_worker_token),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    audio = await storage.get_audio_bytes(job_id)
    if audio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    content, filename = audio
    media_type = "audio/wav" if filename.endswith(".wav") else "application/octet-stream"
    return Response(content=content, media_type=media_type)


@router.post("/jobs/{job_id}/transcribe", response_model=JobResponse)
async def complete_transcription(
    job_id: UUID,
    body: WorkerTranscribeRequest,
    _: None = Depends(verify_worker_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    return await job_service.complete_transcription(
        storage,
        job_id,
        transcript=body.transcript,
    )


@router.post("/jobs/{job_id}/complete-extraction", response_model=JobResponse)
async def complete_extraction(
    job_id: UUID,
    body: WorkerExtractCompleteRequest,
    _: None = Depends(verify_worker_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    return await job_service.complete_extraction(
        storage,
        job_id,
        result=body.result,
    )


@router.post("/jobs/{job_id}/complete-analysis", response_model=JobResponse)
async def complete_analysis(
    job_id: UUID,
    body: WorkerAnalysisCompleteRequest,
    _: None = Depends(verify_worker_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    return await job_service.complete_analysis(
        storage,
        job_id,
        result=body.result,
    )


@router.post("/jobs/{job_id}/fail", response_model=JobResponse)
async def fail_job(
    job_id: UUID,
    body: WorkerFailRequest,
    _: None = Depends(verify_worker_token),
    storage: StorageBackend = Depends(get_storage),
) -> JobResponse:
    return await job_service.fail_job(storage, job_id, error=body.error)

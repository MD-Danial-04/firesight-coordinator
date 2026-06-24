from uuid import UUID

from fastapi import HTTPException, status

from app.schemas import (
    AnalyzeInterviewRequest,
    AnalyzePhotoContext,
    InferenceResult,
    InterviewAnalysisResult,
    InterviewDetailsResult,
    InterviewLanguage,
    JobRecord,
    JobResponse,
    MessageType,
    PhotoAnalysisResult,
    WorkerClaimResponse,
)
from app.storage.protocol import StorageBackend


def job_to_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        job_kind=job.job_kind,
        message_type=job.message_type,
        incident_type_name=job.incident_type_name,
        transcript=job.transcript,
        interview_language=job.interview_language,
        transcript_original=job.transcript_original,
        transcript_english=job.transcript_english,
        analysis_questions=job.analysis_questions,
        result=job.result,
        interview_details_result=job.interview_details_result,
        analysis_result=job.analysis_result,
        photo_path=job.photo_path,
        photo_context=job.photo_context,
        photo_analysis_result=job.photo_analysis_result,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


async def create_job(
    storage: StorageBackend,
    *,
    audio_bytes: bytes,
    filename: str,
    message_type: MessageType,
    incident_type_name: str | None,
    interview_language: InterviewLanguage | None = None,
) -> JobResponse:
    job = await storage.create_job(
        audio_bytes=audio_bytes,
        filename=filename,
        message_type=message_type,
        incident_type_name=incident_type_name,
        interview_language=interview_language,
    )
    return job_to_response(job)


async def create_analyze_job(
    storage: StorageBackend,
    *,
    body: AnalyzeInterviewRequest,
) -> JobResponse:
    job = await storage.create_analyze_job(
        transcript=body.transcript,
        questions=body.questions,
        interview_language=body.interview_language,
    )
    return job_to_response(job)


async def create_photo_analyze_job(
    storage: StorageBackend,
    *,
    image_bytes: bytes,
    filename: str,
    context: AnalyzePhotoContext,
) -> JobResponse:
    job = await storage.create_photo_analyze_job(
        image_bytes=image_bytes,
        filename=filename,
        context=context,
    )
    return job_to_response(job)


async def get_job(storage: StorageBackend, job_id: UUID) -> JobResponse:
    job = await storage.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_response(job)


async def claim_next_job(storage: StorageBackend) -> WorkerClaimResponse | None:
    job = await storage.claim_next_job()
    if job is None:
        return None

    if job.job_kind == "interview_analysis":
        return WorkerClaimResponse(
            job_id=job.id,
            phase="analyze_interview",
            transcript=job.transcript,
            analysis_questions=job.analysis_questions,
            message_type=job.message_type,
            incident_type_name=job.incident_type_name,
            interview_language=job.interview_language,
        )

    if job.job_kind == "photo_analysis":
        return WorkerClaimResponse(
            job_id=job.id,
            phase="analyze_photo",
            image_download_url=storage.image_download_url(job.id),
            photo_context=job.photo_context,
            message_type=job.message_type,
            incident_type_name=job.incident_type_name,
        )

    phase = "extract" if job.transcript else "transcribe"
    return WorkerClaimResponse(
        job_id=job.id,
        phase=phase,
        audio_download_url=storage.audio_download_url(job.id) if phase == "transcribe" else None,
        transcript=job.transcript if phase == "extract" else None,
        message_type=job.message_type,
        incident_type_name=job.incident_type_name,
        interview_language=job.interview_language if phase == "transcribe" else None,
    )


async def complete_transcription(
    storage: StorageBackend,
    job_id: UUID,
    *,
    transcript: str,
    transcript_original: str | None = None,
    transcript_english: str | None = None,
    interview_language: InterviewLanguage | None = None,
) -> JobResponse:
    try:
        job = await storage.complete_transcription(
            job_id,
            transcript=transcript,
            transcript_original=transcript_original,
            transcript_english=transcript_english,
            interview_language=interview_language,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return job_to_response(job)


async def request_extraction(
    storage: StorageBackend,
    job_id: UUID,
    *,
    text: str,
    message_type: MessageType,
    incident_type_name: str | None,
) -> JobResponse:
    try:
        job = await storage.request_extraction(
            job_id,
            text=text,
            message_type=message_type,
            incident_type_name=incident_type_name,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return job_to_response(job)


async def complete_extraction(
    storage: StorageBackend,
    job_id: UUID,
    *,
    result: InferenceResult | None = None,
    interview_details: InterviewDetailsResult | None = None,
) -> JobResponse:
    try:
        job = await storage.complete_extraction(
            job_id,
            result=result,
            interview_details=interview_details,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return job_to_response(job)


async def complete_analysis(
    storage: StorageBackend,
    job_id: UUID,
    *,
    result: InterviewAnalysisResult,
) -> JobResponse:
    try:
        job = await storage.complete_analysis(job_id, result=result)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return job_to_response(job)


async def complete_photo_analysis(
    storage: StorageBackend,
    job_id: UUID,
    *,
    result: PhotoAnalysisResult,
) -> JobResponse:
    try:
        job = await storage.complete_photo_analysis(job_id, result=result)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return job_to_response(job)


async def fail_job(storage: StorageBackend, job_id: UUID, *, error: str) -> JobResponse:
    try:
        job = await storage.fail_job(job_id, error=error)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return job_to_response(job)

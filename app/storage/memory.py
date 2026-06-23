import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.config import settings
from app.schemas import (
    AnalyzePhotoContext,
    InferenceResult,
    InterviewAnalysisResult,
    InterviewLanguage,
    InterviewQuestion,
    JobRecord,
    MessageType,
    PhotoAnalysisResult,
)
from app.storage.protocol import StorageBackend


class MemoryStorage:
    def __init__(self) -> None:
        self._jobs: dict[UUID, JobRecord] = {}
        self._audio: dict[UUID, tuple[bytes, str]] = {}
        self._images: dict[UUID, tuple[bytes, str]] = {}
        self._lock = asyncio.Lock()

    async def create_job(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        message_type: MessageType,
        incident_type_name: str | None,
        interview_language: InterviewLanguage | None = None,
    ) -> JobRecord:
        job_id = uuid4()
        now = datetime.now(UTC)
        audio_path = f"memory://{job_id}/{filename}"
        job = JobRecord(
            id=job_id,
            created_at=now,
            updated_at=now,
            status="pending",
            job_kind="audio_inference",
            audio_path=audio_path,
            message_type=message_type,
            incident_type_name=incident_type_name,
            interview_language=interview_language,
        )
        async with self._lock:
            self._jobs[job_id] = job
            self._audio[job_id] = (audio_bytes, filename)
        return job

    async def create_analyze_job(
        self,
        *,
        transcript: str,
        questions: list[InterviewQuestion],
    ) -> JobRecord:
        job_id = uuid4()
        now = datetime.now(UTC)
        job = JobRecord(
            id=job_id,
            created_at=now,
            updated_at=now,
            status="analyze_pending",
            job_kind="interview_analysis",
            audio_path=None,
            message_type="field_notes",
            transcript=transcript,
            analysis_questions=questions,
        )
        async with self._lock:
            self._jobs[job_id] = job
        return job

    async def create_photo_analyze_job(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        context: AnalyzePhotoContext,
    ) -> JobRecord:
        job_id = uuid4()
        now = datetime.now(UTC)
        photo_path = f"memory://{job_id}/{filename}"
        job = JobRecord(
            id=job_id,
            created_at=now,
            updated_at=now,
            status="analyze_pending",
            job_kind="photo_analysis",
            audio_path=None,
            message_type="field_notes",
            photo_path=photo_path,
            photo_context=context,
        )
        async with self._lock:
            self._jobs[job_id] = job
            self._images[job_id] = (image_bytes, filename)
        return job

    async def get_job(self, job_id: UUID) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def claim_next_job(self) -> JobRecord | None:
        async with self._lock:
            pending = sorted(
                (job for job in self._jobs.values() if job.status == "pending"),
                key=lambda job: job.created_at,
            )
            extract_pending = sorted(
                (job for job in self._jobs.values() if job.status == "extract_pending"),
                key=lambda job: job.created_at,
            )
            analyze_pending = sorted(
                (job for job in self._jobs.values() if job.status == "analyze_pending"),
                key=lambda job: job.created_at,
            )
            candidates = pending or extract_pending or analyze_pending
            if not candidates:
                return None
            job = candidates[0]
            now = datetime.now(UTC)
            claimed = job.model_copy(
                update={"status": "processing", "claimed_at": now, "updated_at": now}
            )
            self._jobs[job.id] = claimed
            return claimed

    async def complete_transcription(
        self,
        job_id: UUID,
        *,
        transcript: str,
        transcript_original: str | None = None,
        transcript_english: str | None = None,
        interview_language: InterviewLanguage | None = None,
    ) -> JobRecord:
        async with self._lock:
            job = self._require_job(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot be transcribed from status {job.status}"
                )
            now = datetime.now(UTC)
            english = transcript_english or transcript
            original = transcript_original or english
            update_fields: dict = {
                "status": "transcribed",
                "transcript": english,
                "transcript_original": original,
                "transcript_english": english,
                "result": None,
                "error": None,
                "updated_at": now,
                "completed_at": None,
            }
            if interview_language is not None:
                update_fields["interview_language"] = interview_language
            updated = job.model_copy(update=update_fields)
            self._jobs[job_id] = updated
            return updated

    async def request_extraction(
        self,
        job_id: UUID,
        *,
        text: str,
        message_type: MessageType,
        incident_type_name: str | None,
    ) -> JobRecord:
        async with self._lock:
            job = self._require_job(job_id)
            if job.status not in ("transcribed", "completed"):
                raise ValueError(
                    f"Job {job_id} cannot request extraction from status {job.status}"
                )
            now = datetime.now(UTC)
            updated = job.model_copy(
                update={
                    "status": "extract_pending",
                    "transcript": text,
                    "result": None,
                    "error": None,
                    "message_type": message_type,
                    "incident_type_name": incident_type_name,
                    "updated_at": now,
                    "completed_at": None,
                }
            )
            self._jobs[job_id] = updated
            return updated

    async def complete_extraction(
        self,
        job_id: UUID,
        *,
        result: InferenceResult,
    ) -> JobRecord:
        async with self._lock:
            job = self._require_job(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot complete extraction from status {job.status}"
                )
            now = datetime.now(UTC)
            updated = job.model_copy(
                update={
                    "status": "completed",
                    "result": result,
                    "error": None,
                    "updated_at": now,
                    "completed_at": now,
                }
            )
            self._jobs[job_id] = updated
            return updated

    async def complete_analysis(
        self,
        job_id: UUID,
        *,
        result: InterviewAnalysisResult,
    ) -> JobRecord:
        async with self._lock:
            job = self._require_job(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot complete analysis from status {job.status}"
                )
            now = datetime.now(UTC)
            updated = job.model_copy(
                update={
                    "status": "completed",
                    "analysis_result": result,
                    "error": None,
                    "updated_at": now,
                    "completed_at": now,
                }
            )
            self._jobs[job_id] = updated
            return updated

    async def complete_photo_analysis(
        self,
        job_id: UUID,
        *,
        result: PhotoAnalysisResult,
    ) -> JobRecord:
        async with self._lock:
            job = self._require_job(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot complete photo analysis from status {job.status}"
                )
            now = datetime.now(UTC)
            updated = job.model_copy(
                update={
                    "status": "completed",
                    "photo_analysis_result": result,
                    "error": None,
                    "updated_at": now,
                    "completed_at": now,
                }
            )
            self._jobs[job_id] = updated
            return updated

    async def fail_job(self, job_id: UUID, *, error: str) -> JobRecord:
        async with self._lock:
            job = self._require_job(job_id)
            if job.status not in ("processing", "pending", "extract_pending", "analyze_pending"):
                raise ValueError(f"Job {job_id} cannot be failed from status {job.status}")
            now = datetime.now(UTC)
            updated = job.model_copy(
                update={
                    "status": "failed",
                    "error": error,
                    "updated_at": now,
                    "completed_at": now,
                }
            )
            self._jobs[job_id] = updated
            return updated

    async def get_audio_bytes(self, job_id: UUID) -> tuple[bytes, str] | None:
        return self._audio.get(job_id)

    async def get_image_bytes(self, job_id: UUID) -> tuple[bytes, str] | None:
        return self._images.get(job_id)

    def audio_download_url(self, job_id: UUID) -> str:
        base = settings.coordinator_base_url.rstrip("/")
        return f"{base}/v1/worker/jobs/{job_id}/audio"

    def image_download_url(self, job_id: UUID) -> str:
        base = settings.coordinator_base_url.rstrip("/")
        return f"{base}/v1/worker/jobs/{job_id}/image"

    def _require_job(self, job_id: UUID) -> JobRecord:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        return job


def create_memory_storage() -> StorageBackend:
    return MemoryStorage()

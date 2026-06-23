import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from supabase import Client, create_client

from app.config import Settings
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

logger = logging.getLogger(__name__)

TABLE = "inference_jobs"


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _row_to_job(row: dict) -> JobRecord:
    result_data = row.get("result")
    result = InferenceResult.model_validate(result_data) if result_data else None
    analysis_result_data = row.get("analysis_result")
    analysis_result = (
        InterviewAnalysisResult.model_validate(analysis_result_data)
        if analysis_result_data
        else None
    )
    questions_data = row.get("analysis_questions")
    analysis_questions = (
        [InterviewQuestion.model_validate(q) for q in questions_data]
        if questions_data
        else None
    )
    photo_context_data = row.get("photo_context")
    photo_context = (
        AnalyzePhotoContext.model_validate(photo_context_data)
        if photo_context_data
        else None
    )
    photo_analysis_result_data = row.get("photo_analysis_result")
    photo_analysis_result = (
        PhotoAnalysisResult.model_validate(photo_analysis_result_data)
        if photo_analysis_result_data
        else None
    )
    return JobRecord(
        id=UUID(str(row["id"])),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        status=row["status"],
        job_kind=row.get("job_kind", "audio_inference"),
        audio_path=row.get("audio_path"),
        message_type=row["message_type"],
        incident_type_name=row.get("incident_type_name"),
        transcript=row.get("transcript"),
        interview_language=row.get("interview_language"),
        transcript_original=row.get("transcript_original"),
        transcript_english=row.get("transcript_english"),
        analysis_questions=analysis_questions,
        result=result,
        analysis_result=analysis_result,
        photo_path=row.get("photo_path"),
        photo_context=photo_context,
        photo_analysis_result=photo_analysis_result,
        error=row.get("error"),
        claimed_at=_parse_datetime(row["claimed_at"]) if row.get("claimed_at") else None,
        completed_at=_parse_datetime(row["completed_at"]) if row.get("completed_at") else None,
    )


class SupabaseStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self._bucket = settings.supabase_audio_bucket
        self._photo_bucket = settings.supabase_photo_bucket

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
        audio_path = f"{job_id}/{filename}"

        def _create() -> JobRecord:
            storage = self._client.storage.from_(self._bucket)
            storage.upload(
                audio_path,
                audio_bytes,
                file_options={"content-type": _content_type(filename), "upsert": "true"},
            )
            row = {
                "id": str(job_id),
                "status": "pending",
                "job_kind": "audio_inference",
                "audio_path": audio_path,
                "message_type": message_type,
                "incident_type_name": incident_type_name,
            }
            if interview_language is not None:
                row["interview_language"] = interview_language
            response = self._client.table(TABLE).insert(row).execute()
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_create)

    async def create_analyze_job(
        self,
        *,
        transcript: str,
        questions: list[InterviewQuestion],
    ) -> JobRecord:
        job_id = uuid4()

        def _create() -> JobRecord:
            row = {
                "id": str(job_id),
                "status": "analyze_pending",
                "job_kind": "interview_analysis",
                "audio_path": None,
                "message_type": "field_notes",
                "transcript": transcript,
                "analysis_questions": [q.model_dump(mode="json") for q in questions],
            }
            response = self._client.table(TABLE).insert(row).execute()
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_create)

    async def create_photo_analyze_job(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        context: AnalyzePhotoContext,
    ) -> JobRecord:
        job_id = uuid4()
        photo_path = f"{job_id}/{filename}"

        def _create() -> JobRecord:
            storage = self._client.storage.from_(self._photo_bucket)
            storage.upload(
                photo_path,
                image_bytes,
                file_options={"content-type": _image_content_type(filename), "upsert": "true"},
            )
            row = {
                "id": str(job_id),
                "status": "analyze_pending",
                "job_kind": "photo_analysis",
                "audio_path": None,
                "message_type": "field_notes",
                "photo_path": photo_path,
                "photo_context": context.model_dump(mode="json"),
            }
            response = self._client.table(TABLE).insert(row).execute()
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_create)

    async def get_job(self, job_id: UUID) -> JobRecord | None:
        def _get() -> JobRecord | None:
            response = (
                self._client.table(TABLE)
                .select("*")
                .eq("id", str(job_id))
                .maybe_single()
                .execute()
            )
            if response.data is None:
                return None
            return _row_to_job(response.data)

        return await asyncio.to_thread(_get)

    async def claim_next_job(self) -> JobRecord | None:
        def _claim() -> JobRecord | None:
            response = self._client.rpc("claim_next_inference_job").execute()
            if not response.data:
                return None
            row = response.data[0] if isinstance(response.data, list) else response.data
            return _row_to_job(row)

        return await asyncio.to_thread(_claim)

    async def complete_transcription(
        self,
        job_id: UUID,
        *,
        transcript: str,
        transcript_original: str | None = None,
        transcript_english: str | None = None,
        interview_language: InterviewLanguage | None = None,
    ) -> JobRecord:
        def _complete() -> JobRecord:
            job = self._require_job_sync(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot be transcribed from status {job.status}"
                )
            english = transcript_english or transcript
            original = transcript_original or english
            update = {
                "status": "transcribed",
                "transcript": english,
                "transcript_original": original,
                "transcript_english": english,
                "result": None,
                "error": None,
                "completed_at": None,
            }
            if interview_language is not None:
                update["interview_language"] = interview_language
            response = (
                self._client.table(TABLE)
                .update(update)
                .eq("id", str(job_id))
                .execute()
            )
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_complete)

    async def request_extraction(
        self,
        job_id: UUID,
        *,
        text: str,
        message_type: MessageType,
        incident_type_name: str | None,
    ) -> JobRecord:
        def _request() -> JobRecord:
            job = self._require_job_sync(job_id)
            if job.status not in ("transcribed", "completed"):
                raise ValueError(
                    f"Job {job_id} cannot request extraction from status {job.status}"
                )
            now = datetime.now(UTC).isoformat()
            update = {
                "status": "extract_pending",
                "transcript": text,
                "message_type": message_type,
                "incident_type_name": incident_type_name,
                "result": None,
                "error": None,
                "completed_at": None,
                "updated_at": now,
            }
            response = (
                self._client.table(TABLE)
                .update(update)
                .eq("id", str(job_id))
                .execute()
            )
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_request)

    async def complete_extraction(
        self,
        job_id: UUID,
        *,
        result: InferenceResult,
    ) -> JobRecord:
        def _complete() -> JobRecord:
            job = self._require_job_sync(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot complete extraction from status {job.status}"
                )
            now = datetime.now(UTC).isoformat()
            update = {
                "status": "completed",
                "result": result.model_dump(mode="json"),
                "error": None,
                "completed_at": now,
            }
            response = (
                self._client.table(TABLE)
                .update(update)
                .eq("id", str(job_id))
                .execute()
            )
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_complete)

    async def complete_analysis(
        self,
        job_id: UUID,
        *,
        result: InterviewAnalysisResult,
    ) -> JobRecord:
        def _complete() -> JobRecord:
            job = self._require_job_sync(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot complete analysis from status {job.status}"
                )
            now = datetime.now(UTC).isoformat()
            update = {
                "status": "completed",
                "analysis_result": result.model_dump(mode="json"),
                "error": None,
                "completed_at": now,
            }
            response = (
                self._client.table(TABLE)
                .update(update)
                .eq("id", str(job_id))
                .execute()
            )
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_complete)

    async def complete_photo_analysis(
        self,
        job_id: UUID,
        *,
        result: PhotoAnalysisResult,
    ) -> JobRecord:
        def _complete() -> JobRecord:
            job = self._require_job_sync(job_id)
            if job.status != "processing":
                raise ValueError(
                    f"Job {job_id} cannot complete photo analysis from status {job.status}"
                )
            now = datetime.now(UTC).isoformat()
            update = {
                "status": "completed",
                "photo_analysis_result": result.model_dump(mode="json"),
                "error": None,
                "completed_at": now,
            }
            response = (
                self._client.table(TABLE)
                .update(update)
                .eq("id", str(job_id))
                .execute()
            )
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_complete)

    async def fail_job(self, job_id: UUID, *, error: str) -> JobRecord:
        def _fail() -> JobRecord:
            job = self._require_job_sync(job_id)
            if job.status not in ("processing", "pending", "extract_pending", "analyze_pending"):
                raise ValueError(f"Job {job_id} cannot be failed from status {job.status}")
            now = datetime.now(UTC).isoformat()
            update = {
                "status": "failed",
                "error": error,
                "completed_at": now,
            }
            response = (
                self._client.table(TABLE)
                .update(update)
                .eq("id", str(job_id))
                .execute()
            )
            return _row_to_job(response.data[0])

        return await asyncio.to_thread(_fail)

    async def get_audio_bytes(self, job_id: UUID) -> tuple[bytes, str] | None:
        def _download() -> tuple[bytes, str] | None:
            job = self._get_job_sync(job_id)
            if job is None or not job.get("audio_path"):
                return None
            audio_path = job["audio_path"]
            filename = audio_path.rsplit("/", 1)[-1]
            data = self._client.storage.from_(self._bucket).download(audio_path)
            return bytes(data), filename

        return await asyncio.to_thread(_download)

    async def get_image_bytes(self, job_id: UUID) -> tuple[bytes, str] | None:
        def _download() -> tuple[bytes, str] | None:
            job = self._get_job_sync(job_id)
            if job is None or not job.get("photo_path"):
                return None
            photo_path = job["photo_path"]
            filename = photo_path.rsplit("/", 1)[-1]
            data = self._client.storage.from_(self._photo_bucket).download(photo_path)
            return bytes(data), filename

        return await asyncio.to_thread(_download)

    def audio_download_url(self, job_id: UUID) -> str:
        base = self._settings.coordinator_base_url.rstrip("/")
        return f"{base}/v1/worker/jobs/{job_id}/audio"

    def image_download_url(self, job_id: UUID) -> str:
        base = self._settings.coordinator_base_url.rstrip("/")
        return f"{base}/v1/worker/jobs/{job_id}/image"

    def _get_job_sync(self, job_id: UUID) -> dict | None:
        response = (
            self._client.table(TABLE)
            .select("*")
            .eq("id", str(job_id))
            .maybe_single()
            .execute()
        )
        return response.data

    def _require_job_sync(self, job_id: UUID) -> JobRecord:
        row = self._get_job_sync(job_id)
        if row is None:
            raise KeyError(f"Job {job_id} not found")
        return _row_to_job(row)


def _content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".wav"):
        return "audio/wav"
    if lower.endswith(".webm"):
        return "audio/webm"
    return "application/octet-stream"


def _image_content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def create_supabase_storage(settings: Settings) -> StorageBackend:
    if not settings.supabase_configured:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return SupabaseStorage(settings)

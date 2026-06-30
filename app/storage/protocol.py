from typing import Protocol
from uuid import UUID

from app.schemas import (
    AnalyzePhotoContext,
    InferenceResult,
    InterviewAnalysisResult,
    InterviewDetailsResult,
    InterviewLanguage,
    InterviewQuestion,
    JobRecord,
    MessageType,
    PhotoAnalysisResult,
)


class StorageBackend(Protocol):
    async def create_job(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        message_type: MessageType,
        incident_type_name: str | None,
        interview_language: InterviewLanguage | None = None,
    ) -> JobRecord: ...

    async def create_analyze_job(
        self,
        *,
        transcript: str,
        questions: list[InterviewQuestion],
        interview_language: InterviewLanguage | None = None,
    ) -> JobRecord: ...

    async def create_photo_analyze_job(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        context: AnalyzePhotoContext,
    ) -> JobRecord: ...

    async def create_clean_transcript_job(
        self,
        *,
        transcript_original: str,
        transcript_english: str,
        interview_language: InterviewLanguage | None = None,
    ) -> JobRecord: ...

    async def get_job(self, job_id: UUID) -> JobRecord | None: ...

    async def claim_next_job(self) -> JobRecord | None: ...

    async def complete_transcription(
        self,
        job_id: UUID,
        *,
        transcript: str,
        transcript_original: str | None = None,
        transcript_english: str | None = None,
        interview_language: InterviewLanguage | None = None,
    ) -> JobRecord: ...

    async def request_extraction(
        self,
        job_id: UUID,
        *,
        text: str,
        message_type: MessageType,
        incident_type_name: str | None,
    ) -> JobRecord: ...

    async def complete_extraction(
        self,
        job_id: UUID,
        *,
        result: InferenceResult | None = None,
        interview_details: InterviewDetailsResult | None = None,
    ) -> JobRecord: ...

    async def complete_analysis(
        self,
        job_id: UUID,
        *,
        result: InterviewAnalysisResult,
    ) -> JobRecord: ...

    async def complete_clean_transcript(
        self,
        job_id: UUID,
        *,
        transcript_original: str,
        transcript_english: str,
    ) -> JobRecord: ...

    async def complete_photo_analysis(
        self,
        job_id: UUID,
        *,
        result: PhotoAnalysisResult,
    ) -> JobRecord: ...

    async def fail_job(self, job_id: UUID, *, error: str) -> JobRecord: ...

    async def get_audio_bytes(self, job_id: UUID) -> tuple[bytes, str] | None: ...

    async def get_image_bytes(self, job_id: UUID) -> tuple[bytes, str] | None: ...

    def audio_download_url(self, job_id: UUID) -> str: ...

    def image_download_url(self, job_id: UUID) -> str: ...

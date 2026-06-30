from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ExtractableField = Literal[
    "applianceCallSign",
    "locationOfFire",
    "fireInvolved",
    "methodOfExtinguishment",
    "damagesSustained",
    "probableCause",
    "ignitionSource",
    "ignitionFuel",
    "eventsCircumstances",
    "areaOfFireOrigin",
    "classification",
    "handoverOfficer",
    "handoverNpc",
]

JobKind = Literal[
    "audio_inference",
    "interview_analysis",
    "photo_analysis",
    "transcript_cleanup",
]
JobStatus = Literal[
    "pending",
    "processing",
    "transcribed",
    "extract_pending",
    "analyze_pending",
    "completed",
    "failed",
]
MessageType = Literal["stop_message", "field_notes", "interview"]
InterviewLanguage = Literal["en", "ms", "ta", "zh"]
ResultSource = Literal["fake", "ollama", "nim", "regex_fallback"]
AnalysisSource = Literal["fake", "ollama", "nim"]
WorkerPhase = Literal[
    "transcribe",
    "extract",
    "analyze_interview",
    "analyze_photo",
    "clean_transcript",
]
QuestionCoverageStatus = Literal["answered", "partial", "unanswered", "unclear"]


class InferenceResult(BaseModel):
    fields: dict[ExtractableField, str]
    confidence: dict[ExtractableField, float]
    source: ResultSource = "fake"


InterviewExtractableField = Literal[
    "name",
    "nameChinese",
    "designation",
    "nric",
    "passportNo",
    "nationality",
    "sex",
    "age",
    "dateAndPlaceOfBirth",
    "maritalStatus",
    "numberOfChildren",
    "citizenshipCertNo",
    "vehicleNo",
    "address",
    "placeOfEmployment",
    "contactHome",
    "contactMobile",
    "contactOffice",
    "interviewTakenPlace",
    "interpretedBy",
]


class InterviewDetailsResult(BaseModel):
    fields: dict[InterviewExtractableField, str]
    confidence: dict[InterviewExtractableField, float]
    source: ResultSource = "fake"


class InterviewQuestion(BaseModel):
    id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    hint: str | None = None
    section: str | None = None


class AnalyzeInterviewRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    questions: list[InterviewQuestion] = Field(..., min_length=1)
    interview_language: InterviewLanguage = "en"


class CleanTranscriptRequest(BaseModel):
    transcript_original: str = Field(..., min_length=1)
    transcript_english: str = Field(..., min_length=1)
    interview_language: InterviewLanguage = "en"


class QuestionCoverage(BaseModel):
    id: str
    status: QuestionCoverageStatus
    answer: str = ""
    evidence: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)


class FollowUpSuggestion(BaseModel):
    related_question_id: str | None = None
    prompt: str
    prompt_conduct: str
    reason: str


class InterviewAnalysisResult(BaseModel):
    coverage: list[QuestionCoverage]
    follow_ups: list[FollowUpSuggestion]
    source: AnalysisSource = "fake"


PhotoAnalysisSource = Literal["fake", "ollama", "nim"]


class PhotoAnalysisResult(BaseModel):
    caption: str
    source: PhotoAnalysisSource = "fake"


class AnalyzePhotoContext(BaseModel):
    location_of_fire: str | None = None
    incident_type_name: str | None = None
    stop_message_excerpt: str | None = None
    field_notes_excerpt: str | None = None


class JobRecord(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    status: JobStatus
    job_kind: JobKind = "audio_inference"
    audio_path: str | None = None
    message_type: MessageType = "stop_message"
    incident_type_name: str | None = None
    transcript: str | None = None
    interview_language: InterviewLanguage | None = None
    transcript_original: str | None = None
    transcript_english: str | None = None
    analysis_questions: list[InterviewQuestion] | None = None
    result: InferenceResult | None = None
    interview_details_result: InterviewDetailsResult | None = None
    analysis_result: InterviewAnalysisResult | None = None
    photo_path: str | None = None
    photo_context: AnalyzePhotoContext | None = None
    photo_analysis_result: PhotoAnalysisResult | None = None
    error: str | None = None
    claimed_at: datetime | None = None
    completed_at: datetime | None = None


class JobResponse(BaseModel):
    id: UUID
    status: JobStatus
    job_kind: JobKind = "audio_inference"
    message_type: MessageType
    incident_type_name: str | None = None
    transcript: str | None = None
    interview_language: InterviewLanguage | None = None
    transcript_original: str | None = None
    transcript_english: str | None = None
    analysis_questions: list[InterviewQuestion] | None = None
    result: InferenceResult | None = None
    interview_details_result: InterviewDetailsResult | None = None
    analysis_result: InterviewAnalysisResult | None = None
    photo_path: str | None = None
    photo_context: AnalyzePhotoContext | None = None
    photo_analysis_result: PhotoAnalysisResult | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class WorkerClaimResponse(BaseModel):
    job_id: UUID
    phase: WorkerPhase
    audio_download_url: str | None = None
    image_download_url: str | None = None
    transcript: str | None = None
    transcript_original: str | None = None
    transcript_english: str | None = None
    analysis_questions: list[InterviewQuestion] | None = None
    photo_context: AnalyzePhotoContext | None = None
    message_type: MessageType
    incident_type_name: str | None = None
    interview_language: InterviewLanguage | None = None


class WorkerTranscribeRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    transcript_original: str | None = None
    transcript_english: str | None = None
    interview_language: InterviewLanguage | None = None


class WorkerExtractCompleteRequest(BaseModel):
    result: InferenceResult | None = None
    interview_details: InterviewDetailsResult | None = None


class WorkerAnalysisCompleteRequest(BaseModel):
    result: InterviewAnalysisResult


class WorkerCleanTranscriptCompleteRequest(BaseModel):
    transcript_original: str
    transcript_english: str


class WorkerPhotoAnalysisCompleteRequest(BaseModel):
    result: PhotoAnalysisResult


class ExtractJobRequest(BaseModel):
    text: str = Field(..., min_length=1)
    message_type: MessageType = "stop_message"
    incident_type_name: str | None = None


class WorkerFailRequest(BaseModel):
    error: str = Field(..., min_length=1)


class LocationPlanResponse(BaseModel):
    matched_address: str
    latitude: float
    longitude: float
    zoom: int
    postal: str | None = None
    image_base64: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    fake_storage: bool
    supabase_configured: bool

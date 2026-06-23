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

JobKind = Literal["audio_inference", "interview_analysis"]
JobStatus = Literal[
    "pending",
    "processing",
    "transcribed",
    "extract_pending",
    "analyze_pending",
    "completed",
    "failed",
]
MessageType = Literal["stop_message", "field_notes"]
ResultSource = Literal["fake", "ollama", "nim", "regex_fallback"]
AnalysisSource = Literal["fake", "ollama", "nim"]
WorkerPhase = Literal["transcribe", "extract", "analyze_interview"]
QuestionCoverageStatus = Literal["answered", "partial", "unanswered", "unclear"]


class InferenceResult(BaseModel):
    fields: dict[ExtractableField, str]
    confidence: dict[ExtractableField, float]
    source: ResultSource = "fake"


class InterviewQuestion(BaseModel):
    id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    hint: str | None = None


class AnalyzeInterviewRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    questions: list[InterviewQuestion] = Field(..., min_length=1)


class QuestionCoverage(BaseModel):
    id: str
    status: QuestionCoverageStatus
    evidence: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)


class FollowUpSuggestion(BaseModel):
    related_question_id: str | None = None
    prompt: str
    reason: str


class InterviewAnalysisResult(BaseModel):
    coverage: list[QuestionCoverage]
    follow_ups: list[FollowUpSuggestion]
    source: AnalysisSource = "fake"


SuggestedPhotoSection = Literal[
    "incident",
    "damages",
    "area_of_origin",
    "burn_patterns",
    "evidentiary",
]

PhotoAnalysisSource = Literal["fake", "ollama", "nim"]


class PhotoAnalysisConfidence(BaseModel):
    caption: float = Field(..., ge=0.0, le=1.0)
    suggested_section: float | None = Field(default=None, ge=0.0, le=1.0)


class PhotoAnalysisResult(BaseModel):
    caption: str
    detected_elements: list[str] = Field(default_factory=list)
    suggested_section: SuggestedPhotoSection | None = None
    confidence: PhotoAnalysisConfidence
    source: PhotoAnalysisSource = "fake"


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
    analysis_questions: list[InterviewQuestion] | None = None
    result: InferenceResult | None = None
    analysis_result: InterviewAnalysisResult | None = None
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
    analysis_questions: list[InterviewQuestion] | None = None
    result: InferenceResult | None = None
    analysis_result: InterviewAnalysisResult | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class WorkerClaimResponse(BaseModel):
    job_id: UUID
    phase: WorkerPhase
    audio_download_url: str | None = None
    transcript: str | None = None
    analysis_questions: list[InterviewQuestion] | None = None
    message_type: MessageType
    incident_type_name: str | None = None


class WorkerTranscribeRequest(BaseModel):
    transcript: str = Field(..., min_length=1)


class WorkerExtractCompleteRequest(BaseModel):
    result: InferenceResult


class WorkerAnalysisCompleteRequest(BaseModel):
    result: InterviewAnalysisResult


class ExtractJobRequest(BaseModel):
    text: str = Field(..., min_length=1)
    message_type: MessageType = "stop_message"
    incident_type_name: str | None = None


class WorkerFailRequest(BaseModel):
    error: str = Field(..., min_length=1)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    fake_storage: bool
    supabase_configured: bool

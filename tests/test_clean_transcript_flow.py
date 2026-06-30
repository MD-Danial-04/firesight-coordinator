from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

WEB_HEADERS = {"Authorization": f"Bearer {settings.web_api_key}"}
WORKER_HEADERS = {"Authorization": f"Bearer {settings.worker_api_key}"}

SAMPLE_ORIGINAL = (
    "Q: Where were you when the fire started?\n"
    "A: I was in the kitchen making dinner.\n"
    "Q: What did you do next?\n"
    "A: I grabbed the extinguisher and called 995."
)
SAMPLE_ENGLISH = SAMPLE_ORIGINAL

CLEANED_ORIGINAL = (
    "I was in the kitchen making dinner.\n"
    "I grabbed the extinguisher and called 995."
)
CLEANED_ENGLISH = CLEANED_ORIGINAL


def test_create_clean_transcript_job_requires_web_auth():
    response = client.post(
        "/v1/clean-transcript",
        json={
            "transcript_original": SAMPLE_ORIGINAL,
            "transcript_english": SAMPLE_ENGLISH,
        },
    )
    assert response.status_code == 401


def test_full_clean_transcript_job_lifecycle():
    create_response = client.post(
        "/v1/clean-transcript",
        headers=WEB_HEADERS,
        json={
            "transcript_original": SAMPLE_ORIGINAL,
            "transcript_english": SAMPLE_ENGLISH,
            "interview_language": "en",
        },
    )
    assert create_response.status_code == 201
    job = create_response.json()
    assert job["status"] == "analyze_pending"
    assert job["job_kind"] == "transcript_cleanup"
    assert job["transcript_original"] == SAMPLE_ORIGINAL
    assert job["transcript_english"] == SAMPLE_ENGLISH
    job_id = job["id"]

    claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim_response.status_code == 200
    claim = claim_response.json()
    assert claim["job_id"] == job_id
    assert claim["phase"] == "clean_transcript"
    assert claim["transcript_original"] == SAMPLE_ORIGINAL
    assert claim["transcript_english"] == SAMPLE_ENGLISH
    assert claim["audio_download_url"] is None

    complete_response = client.post(
        f"/v1/worker/jobs/{job_id}/complete-clean-transcript",
        headers=WORKER_HEADERS,
        json={
            "transcript_original": CLEANED_ORIGINAL,
            "transcript_english": CLEANED_ENGLISH,
        },
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["status"] == "completed"
    assert completed["transcript_original"] == CLEANED_ORIGINAL
    assert completed["transcript_english"] == CLEANED_ENGLISH

    final_response = client.get(f"/v1/jobs/{job_id}", headers=WEB_HEADERS)
    assert final_response.status_code == 200
    final = final_response.json()
    assert final["status"] == "completed"
    assert final["transcript_english"] == CLEANED_ENGLISH


def test_clean_transcript_job_priority_after_audio_jobs():
    audio_response = client.post(
        "/v1/jobs",
        headers=WEB_HEADERS,
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "stop_message"},
    )
    assert audio_response.status_code == 201
    audio_job_id = audio_response.json()["id"]

    clean_response = client.post(
        "/v1/clean-transcript",
        headers=WEB_HEADERS,
        json={
            "transcript_original": SAMPLE_ORIGINAL,
            "transcript_english": SAMPLE_ENGLISH,
        },
    )
    assert clean_response.status_code == 201
    clean_job_id = clean_response.json()["id"]

    claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim_response.status_code == 200
    assert claim_response.json()["job_id"] == audio_job_id
    assert claim_response.json()["phase"] == "transcribe"

    client.post(
        f"/v1/worker/jobs/{audio_job_id}/transcribe",
        headers=WORKER_HEADERS,
        json={"transcript": "LF812 stop."},
    )

    claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim_response.status_code == 200
    assert claim_response.json()["job_id"] == clean_job_id
    assert claim_response.json()["phase"] == "clean_transcript"

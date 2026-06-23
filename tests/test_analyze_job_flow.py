from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

WEB_HEADERS = {"Authorization": f"Bearer {settings.web_api_key}"}
WORKER_HEADERS = {"Authorization": f"Bearer {settings.worker_api_key}"}

SAMPLE_TRANSCRIPT = (
    "The device is a PMD, model Xiaomi M365. It uses a lithium-ion battery. "
    "The battery brand is Samsung."
)

SAMPLE_QUESTIONS = [
    {"id": "device-type", "prompt": "What type of mobility device is it?", "hint": "e.g. PMD"},
    {"id": "device-model", "prompt": "What is the device's model?"},
    {"id": "battery-brand", "prompt": "What is the battery's brand?"},
]

SAMPLE_ANALYSIS_RESULT = {
    "coverage": [
        {
            "id": "device-type",
            "status": "answered",
            "evidence": "The device is a PMD",
            "confidence": 0.95,
        },
        {
            "id": "device-model",
            "status": "answered",
            "evidence": "model Xiaomi M365",
            "confidence": 0.9,
        },
        {
            "id": "battery-brand",
            "status": "answered",
            "evidence": "battery brand is Samsung",
            "confidence": 0.85,
        },
    ],
    "follow_ups": [],
    "source": "fake",
}


def test_create_analyze_job_requires_web_auth():
    response = client.post(
        "/v1/analyze-interview",
        json={"transcript": SAMPLE_TRANSCRIPT, "questions": SAMPLE_QUESTIONS},
    )
    assert response.status_code == 401


def test_full_analyze_job_lifecycle():
    create_response = client.post(
        "/v1/analyze-interview",
        headers=WEB_HEADERS,
        json={"transcript": SAMPLE_TRANSCRIPT, "questions": SAMPLE_QUESTIONS},
    )
    assert create_response.status_code == 201
    job = create_response.json()
    assert job["status"] == "analyze_pending"
    assert job["job_kind"] == "interview_analysis"
    assert job["transcript"] == SAMPLE_TRANSCRIPT
    assert len(job["analysis_questions"]) == 3
    job_id = job["id"]

    claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim_response.status_code == 200
    claim = claim_response.json()
    assert claim["job_id"] == job_id
    assert claim["phase"] == "analyze_interview"
    assert claim["transcript"] == SAMPLE_TRANSCRIPT
    assert len(claim["analysis_questions"]) == 3
    assert claim["audio_download_url"] is None

    complete_response = client.post(
        f"/v1/worker/jobs/{job_id}/complete-analysis",
        headers=WORKER_HEADERS,
        json={"result": SAMPLE_ANALYSIS_RESULT},
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["status"] == "completed"
    assert completed["analysis_result"]["coverage"][0]["status"] == "answered"

    final_response = client.get(f"/v1/jobs/{job_id}", headers=WEB_HEADERS)
    assert final_response.status_code == 200
    final = final_response.json()
    assert final["status"] == "completed"
    assert final["analysis_result"]["source"] == "fake"


def test_analyze_job_priority_after_audio_jobs():
    audio_response = client.post(
        "/v1/jobs",
        headers=WEB_HEADERS,
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "stop_message"},
    )
    assert audio_response.status_code == 201
    audio_job_id = audio_response.json()["id"]

    analyze_response = client.post(
        "/v1/analyze-interview",
        headers=WEB_HEADERS,
        json={"transcript": SAMPLE_TRANSCRIPT, "questions": SAMPLE_QUESTIONS},
    )
    assert analyze_response.status_code == 201
    analyze_job_id = analyze_response.json()["id"]

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
    assert claim_response.json()["job_id"] == analyze_job_id
    assert claim_response.json()["phase"] == "analyze_interview"

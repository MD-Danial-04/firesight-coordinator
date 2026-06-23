from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import ExtractableField

client = TestClient(app)

WEB_HEADERS = {"Authorization": f"Bearer {settings.web_api_key}"}
WORKER_HEADERS = {"Authorization": f"Bearer {settings.worker_api_key}"}

EXTRACTABLE_FIELDS: list[ExtractableField] = [
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

SAMPLE_RESULT = {
    "fields": {field: "" for field in EXTRACTABLE_FIELDS},
    "confidence": {field: 0.0 for field in EXTRACTABLE_FIELDS},
    "source": "fake",
}
SAMPLE_RESULT["fields"]["applianceCallSign"] = "LF812"
SAMPLE_RESULT["fields"]["locationOfFire"] = "7 Gul Ave"
SAMPLE_RESULT["confidence"]["applianceCallSign"] = 0.95
SAMPLE_RESULT["confidence"]["locationOfFire"] = 0.9


def test_create_job_requires_web_auth():
    response = client.post(
        "/v1/jobs",
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "stop_message"},
    )
    assert response.status_code == 401


def test_worker_claim_requires_worker_auth():
    response = client.post("/v1/worker/claim")
    assert response.status_code == 401


def test_create_job_with_invalid_web_key():
    response = client.post(
        "/v1/jobs",
        headers={"Authorization": "Bearer wrong-key"},
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "stop_message"},
    )
    assert response.status_code == 401


def test_full_fake_job_lifecycle():
    create_response = client.post(
        "/v1/jobs",
        headers=WEB_HEADERS,
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={
            "message_type": "stop_message",
            "incident_type_name": "False Alarm Malfunction",
        },
    )
    assert create_response.status_code == 201
    job = create_response.json()
    assert job["status"] == "pending"
    job_id = job["id"]

    get_response = client.get(f"/v1/jobs/{job_id}", headers=WEB_HEADERS)
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "pending"

    claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim_response.status_code == 200
    claim = claim_response.json()
    assert claim["job_id"] == job_id
    assert claim["phase"] == "transcribe"
    assert claim["audio_download_url"].endswith(f"/v1/worker/jobs/{job_id}/audio")
    assert claim["transcript"] is None

    audio_response = client.get(claim["audio_download_url"], headers=WORKER_HEADERS)
    assert audio_response.status_code == 200
    assert audio_response.content == b"audio-bytes"

    transcribe_response = client.post(
        f"/v1/worker/jobs/{job_id}/transcribe",
        headers=WORKER_HEADERS,
        json={
            "transcript": "LF812 stop for location at 7 Gul Ave.",
        },
    )
    assert transcribe_response.status_code == 200
    transcribed = transcribe_response.json()
    assert transcribed["status"] == "transcribed"
    assert transcribed["transcript"] == "LF812 stop for location at 7 Gul Ave."
    assert transcribed["result"] is None

    extract_request_response = client.post(
        f"/v1/jobs/{job_id}/extract",
        headers=WEB_HEADERS,
        json={
            "text": "LF812 stop for location at 7 Gul Ave. Updated by user.",
            "message_type": "stop_message",
            "incident_type_name": "False Alarm Malfunction",
        },
    )
    assert extract_request_response.status_code == 200
    extract_requested = extract_request_response.json()
    assert extract_requested["status"] == "extract_pending"
    assert extract_requested["transcript"] == "LF812 stop for location at 7 Gul Ave. Updated by user."

    extract_claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert extract_claim_response.status_code == 200
    extract_claim = extract_claim_response.json()
    assert extract_claim["phase"] == "extract"
    assert extract_claim["audio_download_url"] is None
    assert extract_claim["transcript"] == "LF812 stop for location at 7 Gul Ave. Updated by user."

    complete_extraction_response = client.post(
        f"/v1/worker/jobs/{job_id}/complete-extraction",
        headers=WORKER_HEADERS,
        json={"result": SAMPLE_RESULT},
    )
    assert complete_extraction_response.status_code == 200
    completed = complete_extraction_response.json()
    assert completed["status"] == "completed"
    assert completed["result"]["fields"]["applianceCallSign"] == "LF812"

    final_response = client.get(f"/v1/jobs/{job_id}", headers=WEB_HEADERS)
    assert final_response.status_code == 200
    final = final_response.json()
    assert final["status"] == "completed"
    assert final["result"]["fields"]["locationOfFire"] == "7 Gul Ave"


def test_fail_job():
    create_response = client.post(
        "/v1/jobs",
        headers=WEB_HEADERS,
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "stop_message"},
    )
    job_id = create_response.json()["id"]

    client.post("/v1/worker/claim", headers=WORKER_HEADERS)

    fail_response = client.post(
        f"/v1/worker/jobs/{job_id}/fail",
        headers=WORKER_HEADERS,
        json={"error": "Whisper model failed to load"},
    )
    assert fail_response.status_code == 200
    assert fail_response.json()["status"] == "failed"
    assert fail_response.json()["error"] == "Whisper model failed to load"

"""End-to-end job lifecycle via coordinator TestClient (in-memory storage)."""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

WEB_HEADERS = {"Authorization": f"Bearer {settings.web_api_key}"}
WORKER_HEADERS = {"Authorization": f"Bearer {settings.worker_api_key}"}

SAMPLE_RESULT = {
    "fields": {
        "applianceCallSign": "LF812",
        "locationOfFire": "7 Gul Ave",
        "fireInvolved": "False alarm",
        "methodOfExtinguishment": "",
        "damagesSustained": "",
        "probableCause": "",
        "ignitionSource": "",
        "ignitionFuel": "",
        "eventsCircumstances": "",
        "areaOfFireOrigin": "",
        "classification": "",
        "handoverOfficer": "",
        "handoverNpc": "",
    },
    "confidence": {"applianceCallSign": 0.95, "locationOfFire": 0.9},
    "source": "fake",
}


def test_e2e_upload_claim_transcribe_extract_complete():
    create = client.post(
        "/v1/jobs",
        headers=WEB_HEADERS,
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "stop_message", "incident_type_name": "Fire"},
    )
    assert create.status_code == 201
    job_id = create.json()["id"]

    claim = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim.status_code == 200
    assert claim.json()["job_id"] == job_id
    assert claim.json()["phase"] == "transcribe"

    audio = client.get(f"/v1/worker/jobs/{job_id}/audio", headers=WORKER_HEADERS)
    assert audio.status_code == 200
    assert audio.content == b"audio-bytes"

    transcribe = client.post(
        f"/v1/worker/jobs/{job_id}/transcribe",
        headers=WORKER_HEADERS,
        json={
            "transcript": "LF812 stop for location at 7 Gul Ave.",
        },
    )
    assert transcribe.status_code == 200
    body = transcribe.json()
    assert body["status"] == "transcribed"
    assert body["transcript"] == "LF812 stop for location at 7 Gul Ave."

    extract_request = client.post(
        f"/v1/jobs/{job_id}/extract",
        headers=WEB_HEADERS,
        json={
            "text": "LF812 stop for location at 7 Gul Ave. Edited transcript.",
            "message_type": "stop_message",
            "incident_type_name": "Fire",
        },
    )
    assert extract_request.status_code == 200
    assert extract_request.json()["status"] == "extract_pending"

    extract_claim = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert extract_claim.status_code == 200
    assert extract_claim.json()["phase"] == "extract"
    assert extract_claim.json()["transcript"] == "LF812 stop for location at 7 Gul Ave. Edited transcript."

    complete_extraction = client.post(
        f"/v1/worker/jobs/{job_id}/complete-extraction",
        headers=WORKER_HEADERS,
        json={"result": SAMPLE_RESULT},
    )
    assert complete_extraction.status_code == 200
    extraction_body = complete_extraction.json()
    assert extraction_body["status"] == "completed"
    assert extraction_body["result"]["fields"]["applianceCallSign"] == "LF812"

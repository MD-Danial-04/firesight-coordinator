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
SAMPLE_INTERVIEW_DETAILS = {
    "fields": {
        "name": "John Tan",
        "nameChinese": "",
        "designation": "Tenant",
        "nric": "S1234567A",
        "passportNo": "",
        "nationality": "Singaporean",
        "sex": "",
        "age": "",
        "dateAndPlaceOfBirth": "",
        "maritalStatus": "",
        "numberOfChildren": "",
        "citizenshipCertNo": "",
        "vehicleNo": "",
        "address": "",
        "placeOfEmployment": "",
        "contactHome": "",
        "contactMobile": "91234567",
        "contactOffice": "",
        "interviewTakenPlace": "",
        "interpretedBy": "",
    },
    "confidence": {
        "name": 0.9,
        "nameChinese": 0.0,
        "designation": 0.8,
        "nric": 0.95,
        "passportNo": 0.0,
        "nationality": 0.7,
        "sex": 0.0,
        "age": 0.0,
        "dateAndPlaceOfBirth": 0.0,
        "maritalStatus": 0.0,
        "numberOfChildren": 0.0,
        "citizenshipCertNo": 0.0,
        "vehicleNo": 0.0,
        "address": 0.0,
        "placeOfEmployment": 0.0,
        "contactHome": 0.0,
        "contactMobile": 0.9,
        "contactOffice": 0.0,
        "interviewTakenPlace": 0.0,
        "interpretedBy": 0.0,
    },
    "source": "fake",
}


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


def test_interview_extraction_lifecycle():
    create_response = client.post(
        "/v1/jobs",
        headers=WEB_HEADERS,
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "interview", "interview_language": "en"},
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim_response.status_code == 200
    assert claim_response.json()["phase"] == "transcribe"
    assert claim_response.json()["message_type"] == "interview"

    transcribe_response = client.post(
        f"/v1/worker/jobs/{job_id}/transcribe",
        headers=WORKER_HEADERS,
        json={"transcript": "My name is John Tan."},
    )
    assert transcribe_response.status_code == 200

    extract_request_response = client.post(
        f"/v1/jobs/{job_id}/extract",
        headers=WEB_HEADERS,
        json={
            "text": "My name is John Tan. NRIC S1234567A. Contact 91234567.",
            "message_type": "interview",
            "incident_type_name": None,
        },
    )
    assert extract_request_response.status_code == 200
    assert extract_request_response.json()["status"] == "extract_pending"

    extract_claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert extract_claim_response.status_code == 200
    assert extract_claim_response.json()["phase"] == "extract"
    assert extract_claim_response.json()["message_type"] == "interview"

    complete_extraction_response = client.post(
        f"/v1/worker/jobs/{job_id}/complete-extraction",
        headers=WORKER_HEADERS,
        json={"interview_details": SAMPLE_INTERVIEW_DETAILS},
    )
    assert complete_extraction_response.status_code == 200
    completed = complete_extraction_response.json()
    assert completed["status"] == "completed"
    assert completed["interview_details_result"]["fields"]["name"] == "John Tan"
    assert completed["result"] is None

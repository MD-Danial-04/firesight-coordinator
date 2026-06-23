from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

WEB_HEADERS = {"Authorization": f"Bearer {settings.web_api_key}"}
WORKER_HEADERS = {"Authorization": f"Bearer {settings.worker_api_key}"}

SAMPLE_IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-bytes"

SAMPLE_PHOTO_ANALYSIS_RESULT = {
    "caption": "Charring observed on ceiling lining above seating area.",
    "detected_elements": ["ceiling charring", "smoke staining"],
    "suggested_section": "burn_patterns",
    "section_candidates": {
        "incident": {"score": 0.15, "reason": None},
        "damages": {"score": 0.4, "reason": None},
        "area_of_origin": {"score": 0.35, "reason": None},
        "burn_patterns": {"score": 0.85, "reason": "ceiling charring visible"},
        "evidentiary": {"score": 0.2, "reason": None},
    },
    "confidence": {"caption": 0.85, "suggested_section": 0.85},
    "source": "fake",
}


def test_create_photo_job_requires_web_auth():
    response = client.post(
        "/v1/analyze-photo",
        files={"file": ("scene.jpg", SAMPLE_IMAGE_BYTES, "image/jpeg")},
    )
    assert response.status_code == 401


def test_full_photo_analyze_job_lifecycle():
    create_response = client.post(
        "/v1/analyze-photo",
        headers=WEB_HEADERS,
        files={"file": ("scene.jpg", SAMPLE_IMAGE_BYTES, "image/jpeg")},
        data={
            "location_of_fire": "7 Gul Ave",
            "incident_type_name": "Structure Fire",
        },
    )
    assert create_response.status_code == 201
    job = create_response.json()
    assert job["status"] == "analyze_pending"
    assert job["job_kind"] == "photo_analysis"
    assert job["photo_context"]["location_of_fire"] == "7 Gul Ave"
    job_id = job["id"]

    claim_response = client.post("/v1/worker/claim", headers=WORKER_HEADERS)
    assert claim_response.status_code == 200
    claim = claim_response.json()
    assert claim["job_id"] == job_id
    assert claim["phase"] == "analyze_photo"
    assert claim["image_download_url"] is not None
    assert claim["photo_context"]["location_of_fire"] == "7 Gul Ave"
    assert claim["audio_download_url"] is None

    image_response = client.get(
        f"/v1/worker/jobs/{job_id}/image",
        headers=WORKER_HEADERS,
    )
    assert image_response.status_code == 200
    assert image_response.content == SAMPLE_IMAGE_BYTES

    complete_response = client.post(
        f"/v1/worker/jobs/{job_id}/complete-photo-analysis",
        headers=WORKER_HEADERS,
        json={"result": SAMPLE_PHOTO_ANALYSIS_RESULT},
    )
    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["status"] == "completed"
    assert completed["photo_analysis_result"]["suggested_section"] == "burn_patterns"
    assert completed["photo_analysis_result"]["section_candidates"]["burn_patterns"]["score"] == 0.85

    final_response = client.get(f"/v1/jobs/{job_id}", headers=WEB_HEADERS)
    assert final_response.status_code == 200
    final = final_response.json()
    assert final["status"] == "completed"
    assert final["photo_analysis_result"]["source"] == "fake"


def test_photo_job_priority_after_audio_jobs():
    audio_response = client.post(
        "/v1/jobs",
        headers=WEB_HEADERS,
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
        data={"message_type": "stop_message"},
    )
    assert audio_response.status_code == 201
    audio_job_id = audio_response.json()["id"]

    photo_response = client.post(
        "/v1/analyze-photo",
        headers=WEB_HEADERS,
        files={"file": ("scene.jpg", SAMPLE_IMAGE_BYTES, "image/jpeg")},
    )
    assert photo_response.status_code == 201
    photo_job_id = photo_response.json()["id"]

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
    assert claim_response.json()["job_id"] == photo_job_id
    assert claim_response.json()["phase"] == "analyze_photo"

import base64

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import onemap

client = TestClient(app)

WEB_HEADERS = {"Authorization": f"Bearer {settings.web_api_key}"}

SAMPLE_PNG = b"\x89PNG\r\n\x1a\nfake-image-bytes"


def test_location_plan_requires_web_auth():
    response = client.get("/v1/location-plan", params={"address": "640 Rowell Road"})
    assert response.status_code == 401


def test_location_plan_success(monkeypatch: pytest.MonkeyPatch):
    async def fake_geocode(_client, address: str) -> onemap.GeocodeResult:
        assert address == "640 Rowell Road"
        return onemap.GeocodeResult(
            matched_address="640 ROWELL ROAD SINGAPORE 200640",
            latitude=1.30743547948389,
            longitude=103.854713903431,
            postal="200640",
        )

    async def fake_static_map(_client, **kwargs) -> bytes:
        assert kwargs["zoom"] == 18
        assert kwargs["latitude"] == 1.30743547948389
        return SAMPLE_PNG

    monkeypatch.setattr(onemap, "geocode", fake_geocode)
    monkeypatch.setattr(onemap, "static_map", fake_static_map)

    response = client.get(
        "/v1/location-plan",
        headers=WEB_HEADERS,
        params={"address": "640 Rowell Road", "zoom": 18},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched_address"] == "640 ROWELL ROAD SINGAPORE 200640"
    assert body["latitude"] == 1.30743547948389
    assert body["longitude"] == 103.854713903431
    assert body["zoom"] == 18
    assert body["postal"] == "200640"
    assert base64.b64decode(body["image_base64"]) == SAMPLE_PNG


def test_location_plan_address_not_found(monkeypatch: pytest.MonkeyPatch):
    async def fake_geocode(_client, address: str) -> onemap.GeocodeResult:
        raise onemap.OneMapAddressNotFound(f"No OneMap match for address: {address}")

    monkeypatch.setattr(onemap, "geocode", fake_geocode)

    response = client.get(
        "/v1/location-plan",
        headers=WEB_HEADERS,
        params={"address": "nowhere at all"},
    )
    assert response.status_code == 404


def test_location_plan_upstream_error(monkeypatch: pytest.MonkeyPatch):
    async def fake_geocode(_client, address: str) -> onemap.GeocodeResult:
        raise onemap.OneMapError("OneMap search failed (500)")

    monkeypatch.setattr(onemap, "geocode", fake_geocode)

    response = client.get(
        "/v1/location-plan",
        headers=WEB_HEADERS,
        params={"address": "640 Rowell Road"},
    )
    assert response.status_code == 502


def test_location_plan_zoom_out_of_range():
    response = client.get(
        "/v1/location-plan",
        headers=WEB_HEADERS,
        params={"address": "640 Rowell Road", "zoom": 99},
    )
    assert response.status_code == 422

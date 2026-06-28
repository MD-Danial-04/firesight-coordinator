"""OneMap (Singapore SLA) geocoding + static map proxy.

The Search API requires a bearer token minted from the email/password
credentials. The static map service does not strictly require the token, but we
send it when available for consistency. Tokens are valid for ~3 days; we cache
the token in-process and refresh on expiry or on a 401 response.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.config import settings

# Refresh slightly before the advertised expiry to avoid edge-of-expiry races.
_TOKEN_REFRESH_SKEW_SECONDS = 60


class OneMapError(RuntimeError):
    """Raised when a OneMap request cannot be completed."""


class OneMapNotConfigured(OneMapError):
    """Raised when OneMap credentials are missing."""


class OneMapAddressNotFound(OneMapError):
    """Raised when the address yields no geocoding results."""


@dataclass
class GeocodeResult:
    matched_address: str
    latitude: float
    longitude: float
    postal: str | None


# In-process token cache: (token, unix_expiry_seconds).
_cached_token: tuple[str, float] | None = None


def reset_token_cache_for_tests() -> None:
    global _cached_token
    _cached_token = None


async def get_token(client: httpx.AsyncClient, *, force_refresh: bool = False) -> str:
    """Return a valid OneMap access token, minting/refreshing as needed."""
    global _cached_token

    if not settings.onemap_configured:
        raise OneMapNotConfigured(
            "OneMap credentials are not configured (ONEMAP_EMAIL / ONEMAP_PASSWORD)"
        )

    now = time.time()
    if (
        not force_refresh
        and _cached_token is not None
        and _cached_token[1] - _TOKEN_REFRESH_SKEW_SECONDS > now
    ):
        return _cached_token[0]

    url = f"{settings.onemap_base_url}/api/auth/post/getToken"
    try:
        response = await client.post(
            url,
            json={"email": settings.onemap_email, "password": settings.onemap_password},
        )
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise OneMapError(f"OneMap auth request failed: {exc}") from exc

    if response.status_code != 200:
        raise OneMapError(
            f"OneMap auth failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    token = data.get("access_token")
    if not token:
        raise OneMapError("OneMap auth response did not include an access token")

    try:
        expiry = float(data.get("expiry_timestamp", now + 3 * 24 * 3600))
    except (TypeError, ValueError):
        expiry = now + 3 * 24 * 3600

    _cached_token = (token, expiry)
    return token


async def geocode(client: httpx.AsyncClient, address: str) -> GeocodeResult:
    """Resolve a free-text address/postal code to its top OneMap match."""
    query = address.strip()
    if not query:
        raise OneMapAddressNotFound("Empty address")

    url = f"{settings.onemap_base_url}/api/common/elastic/search"
    params = {
        "searchVal": query,
        "returnGeom": "Y",
        "getAddrDetails": "Y",
        "pageNum": "1",
    }

    async def _request(token: str) -> httpx.Response:
        return await client.get(url, params=params, headers={"Authorization": token})

    token = await get_token(client)
    try:
        response = await _request(token)
        if response.status_code == 401:
            token = await get_token(client, force_refresh=True)
            response = await _request(token)
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise OneMapError(f"OneMap search request failed: {exc}") from exc

    if response.status_code != 200:
        raise OneMapError(
            f"OneMap search failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    results = data.get("results") or []
    if not results:
        raise OneMapAddressNotFound(f"No OneMap match for address: {address}")

    top = results[0]
    try:
        latitude = float(top["LATITUDE"])
        longitude = float(top["LONGITUDE"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OneMapError("OneMap result missing coordinates") from exc

    postal = top.get("POSTAL")
    if postal in ("NIL", ""):
        postal = None

    return GeocodeResult(
        matched_address=top.get("ADDRESS") or top.get("SEARCHVAL") or query,
        latitude=latitude,
        longitude=longitude,
        postal=postal,
    )


async def static_map(
    client: httpx.AsyncClient,
    *,
    latitude: float,
    longitude: float,
    zoom: int,
    width: int = 512,
    height: int = 512,
) -> bytes:
    """Fetch a static map PNG centred on the point with a marker."""
    url = f"{settings.onemap_base_url}/api/staticmap/getStaticImage"
    params = {
        "layerchosen": "default",
        "latitude": f"{latitude}",
        "longitude": f"{longitude}",
        "zoom": str(zoom),
        "width": str(width),
        "height": str(height),
        "points": f"[{latitude},{longitude}]",
        "color": "255,0,0",
    }

    headers: dict[str, str] = {}
    if settings.onemap_configured:
        headers["Authorization"] = await get_token(client)

    try:
        response = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise OneMapError(f"OneMap static map request failed: {exc}") from exc

    if response.status_code != 200:
        raise OneMapError(
            f"OneMap static map failed ({response.status_code}): {response.text}"
        )

    return response.content

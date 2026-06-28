import base64

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import verify_web_token
from app.schemas import LocationPlanResponse
from app.services import onemap

router = APIRouter(prefix="/v1", tags=["location"])

# OneMap static map caps width/height at 512px.
_MAP_SIZE = 512
_MIN_ZOOM = 11
_MAX_ZOOM = 19


@router.get("/location-plan", response_model=LocationPlanResponse)
async def get_location_plan(
    address: str = Query(..., min_length=1),
    zoom: int = Query(default=17, ge=_MIN_ZOOM, le=_MAX_ZOOM),
    _: None = Depends(verify_web_token),
) -> LocationPlanResponse:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            geocoded = await onemap.geocode(client, address)
            image_bytes = await onemap.static_map(
                client,
                latitude=geocoded.latitude,
                longitude=geocoded.longitude,
                zoom=zoom,
                width=_MAP_SIZE,
                height=_MAP_SIZE,
            )
        except onemap.OneMapNotConfigured as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except onemap.OneMapAddressNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except onemap.OneMapError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

    return LocationPlanResponse(
        matched_address=geocoded.matched_address,
        latitude=geocoded.latitude,
        longitude=geocoded.longitude,
        zoom=zoom,
        postal=geocoded.postal,
        image_base64=base64.b64encode(image_bytes).decode("ascii"),
    )

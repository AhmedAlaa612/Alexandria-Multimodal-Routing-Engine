"""
REST transport layer for the Geocoding API.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from geocoding_api.geocoder.forward import geocode
from geocoding_api.schemas.models import (
    GeocodeResponse, GeocodeResult, HealthResponse,
)

router = APIRouter(prefix="/api/v1", tags=["geocoding"])


@router.get("/geocode", response_model=GeocodeResponse)
async def forward_geocode(
    address: str = Query(..., description="Address to geocode"),
    language: str = Query("en", description="Language (en, ar, etc.)"),
    bias: bool = Query(True, description="Bias results to Alexandria"),
    user_lat: Optional[float] = Query(None, description="User latitude for proximity ranking"),
    user_lng: Optional[float] = Query(None, description="User longitude for proximity ranking"),
):
    """Forward geocode an address to coordinates."""
    if not address or not address.strip():
        raise HTTPException(status_code=400, detail="Missing required parameter: address")

    try:
        raw_results = geocode(
            address=address,
            language=language,
            bias=bias,
            user_lat=user_lat,
            user_lng=user_lng,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geocoding failed: {e}")

    if not raw_results:
        return GeocodeResponse(
            success=False,
            query=address,
            language=language,
            bias=bias,
            count=0,
            results=[],
            error=f"No results found{'within Alexandria' if bias else ''} for: \"{address}\""
                  + (". Use bias=false to search globally." if bias else ""),
        )

    results = [GeocodeResult(**r) for r in raw_results]
    return GeocodeResponse(
        success=True,
        query=address,
        language=language,
        bias=bias,
        count=len(results),
        results=results,
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    """Service health check."""
    return HealthResponse(status="ok")

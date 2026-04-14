"""
REST transport layer for DB Tools API.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from db_tools.db.queries import get_nearby_trips
from db_tools.schemas.models import (
    NearbyTripsQuery, NearbyTripsResponse, NearbyTrip, HealthResponse,
)
from db_tools.db.pool import get_pool

router = APIRouter(prefix="/api/v1", tags=["db-tools"])


@router.get("/nearby-trips", response_model=NearbyTripsResponse)
async def nearby_trips(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_m: float = Query(1000.0, gt=0, description="Search radius in meters"),
    starts: bool = Query(False, description="If true, only trips whose start stop is within radius"),
    epsg: int = Query(32636, description="Projected CRS EPSG"),
):
    """Find all transit trips with at least one stop within the search radius."""
    try:
        rows = get_nearby_trips(
            lat=lat, lon=lon, radius_m=radius_m, starts=starts, epsg=epsg,
        )
        trips = [NearbyTrip(**row) for row in rows]
        return NearbyTripsResponse(
            query=NearbyTripsQuery(
                lat=lat, lon=lon, radius_m=radius_m, starts=starts, epsg=epsg,
            ),
            count=len(trips),
            trips=trips,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health", response_model=HealthResponse)
async def health():
    """Service health check with DB connectivity test."""
    try:
        pool = get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return HealthResponse(status="ok", db_connected=True)
        finally:
            pool.putconn(conn)
    except Exception:
        return HealthResponse(status="degraded", db_connected=False)

"""
Pydantic models for DB Tools API.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Nearby Trips ──────────────────────────────────────────────────────────────

class NearbyTripsQuery(BaseModel):
    lat: float = Field(..., description="Query latitude")
    lon: float = Field(..., description="Query longitude")
    radius_m: float = Field(1000.0, gt=0, description="Search radius in meters")
    starts: bool = Field(False, description="If true, only trips whose start stop is within radius")
    epsg: int = Field(32636, description="Projected CRS EPSG for distance calculation")


class NearbyStop(BaseModel):
    closest_stop_id: str
    closest_stop_name: Optional[str] = None
    closest_stop_name_ar: Optional[str] = None
    closest_stop_lat: Optional[float] = None
    closest_stop_lon: Optional[float] = None
    closest_stop_sequence: Optional[int] = None


class NearbyTrip(BaseModel):
    trip_id: str
    route_id: Optional[str] = None
    trip_headsign: Optional[str] = None
    trip_headsign_ar: Optional[str] = None
    direction_id: Optional[int] = None
    route_short_name: Optional[str] = None
    route_short_name_ar: Optional[str] = None
    route_name: Optional[str] = None
    route_name_ar: Optional[str] = None
    distance_m: Optional[float] = None
    # Closest stop info (flattened from SQL)
    closest_stop_id: Optional[str] = None
    closest_stop_name: Optional[str] = None
    closest_stop_name_ar: Optional[str] = None
    closest_stop_lat: Optional[float] = None
    closest_stop_lon: Optional[float] = None
    closest_stop_sequence: Optional[int] = None


class NearbyTripsResponse(BaseModel):
    query: NearbyTripsQuery
    count: int
    trips: list[NearbyTrip]


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    db_connected: bool = False

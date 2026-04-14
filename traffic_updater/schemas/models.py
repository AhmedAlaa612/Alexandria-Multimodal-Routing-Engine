"""
Pydantic models for the traffic updater API.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TriggerRequest(BaseModel):
    trip_ids: Optional[list[str]] = None  # None = update all trips
    notify_routing_api: bool = True


class UpdateTripRequest(BaseModel):
    trip_id: str
    notify_routing_api: bool = True


class UpdateResponse(BaseModel):
    status: str
    trips_updated: int = 0
    trips_failed: int = 0
    message: str = ""


class StatusResponse(BaseModel):
    status: str = "idle"
    last_update: Optional[str] = None
    trips_in_data: int = 0
    is_running: bool = False


# ── Street traffic ────────────────────────────────────────────────────────────

class StreetTrafficLeg(BaseModel):
    distance_m: int = 0
    distance_text: str = ""
    duration_seconds: int = 0
    duration_text: str = ""
    status: str = "unknown"  # 'clear', 'moderate', 'heavy'


class StreetTrafficRoute(BaseModel):
    label: str = ""
    distance_m: int = 0
    distance_text: str = ""
    duration_seconds: int = 0
    duration_text: str = ""


class StreetTrafficResponse(BaseModel):
    street: str
    street_ar: str = ""
    segments: int = 0
    waypoints_used: int = 0
    total_distance_km: float = 0
    total_duration_min: float = 0
    total_duration_normal_s: int = 0  # Expected time at 40 km/hr
    overall_status: str = "unknown"  # 'clear', 'moderate', 'heavy'
    legs: list[StreetTrafficLeg] = []
    routes: list[StreetTrafficRoute] = []
    error: Optional[str] = None


class StreetInfo(BaseModel):
    name: str
    name_ar: str = ""
    aliases: list[str] = []
    segments: int = 0
    total_length_km: float = 0


class StreetListResponse(BaseModel):
    count: int
    streets: list[StreetInfo] = []


"""
REST transport layer for the traffic updater service.
"""

import threading

from fastapi import APIRouter, Query

from traffic_updater.schemas.models import (
    TriggerRequest, UpdateTripRequest, UpdateResponse, StatusResponse,
    StreetTrafficResponse, StreetTrafficLeg, StreetTrafficRoute,
    StreetInfo, StreetListResponse,
)
from traffic_updater.updater.prefix_times import (
    update_all_trips, update_single_trip, get_status,
)
from traffic_updater.streets.traffic import (
    get_street_traffic, get_available_streets,
)

router = APIRouter(prefix="/api/v1", tags=["traffic-update"])


# ── Trip update endpoints ────────────────────────────────────────────────────

@router.post("/update/trigger", response_model=UpdateResponse)
async def trigger_update(req: TriggerRequest = TriggerRequest()):
    """
    Trigger a full travel-time update cycle.

    Runs in a background thread so the request returns immediately.
    """
    status = get_status()
    if status["is_running"]:
        return UpdateResponse(status="error", message="Update already in progress")

    def _run():
        update_all_trips(notify=req.notify_routing_api)

    threading.Thread(target=_run, daemon=True).start()
    return UpdateResponse(status="started", message="Update started in background")


@router.get("/update/status", response_model=StatusResponse)
async def update_status():
    """Get current update status."""
    return StatusResponse(**get_status())


@router.post("/update/trip/{trip_id}", response_model=UpdateResponse)
async def update_trip(trip_id: str, req: UpdateTripRequest = None):
    """Update travel times for a single trip (synchronous)."""
    notify = req.notify_routing_api if req else True
    result = update_single_trip(trip_id, notify=notify)
    return UpdateResponse(**result)


# ── Street traffic endpoints ─────────────────────────────────────────────────

@router.get("/traffic/streets", response_model=StreetListResponse)
async def list_streets():
    """List all available main streets with metadata."""
    streets_raw = get_available_streets()
    streets = [StreetInfo(**s) for s in streets_raw]
    return StreetListResponse(count=len(streets), streets=streets)


@router.get("/traffic/street", response_model=StreetTrafficResponse)
async def street_traffic(
    name: str = Query(..., description="Street group name (e.g. 'Abou Qir', 'Coastal', 'Mahmoudia', 'Moustafa Kamel')"),
    language: str = Query("en", description="Language for Google Maps results"),
    max_waypoints: int = Query(20, ge=2, le=25, description="Max waypoints to send to Google Maps"),
):
    """
    Get live traffic info for a main street from Google Maps.

    Loads GeoJSON road segments for the street, samples waypoints,
    and queries Google Maps directions for traffic-aware travel times.
    
    Response includes per-segment status and an overall street status.
    """
    result = get_street_traffic(
        street_name=name,
        language=language,
        max_waypoints=max_waypoints,
    )

    legs = [StreetTrafficLeg(**leg) for leg in result.get("legs", [])]
    routes = [StreetTrafficRoute(**r) for r in result.get("routes", [])]

    return StreetTrafficResponse(
        street=result.get("street", name),
        street_ar=result.get("street_ar", ""),
        segments=result.get("segments", 0),
        waypoints_used=result.get("waypoints_used", 0),
        total_distance_km=result.get("total_distance_km", 0),
        total_duration_min=result.get("total_duration_min", 0),
        total_duration_normal_s=result.get("total_duration_normal_s", 0),
        overall_status=result.get("overall_status", "unknown"),
        legs=legs,
        routes=routes,
        error=result.get("error"),
    )


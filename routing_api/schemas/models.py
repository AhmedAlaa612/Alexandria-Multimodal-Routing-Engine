"""
Pydantic request / response models for the routing API.
Shared between REST and gRPC transport layers.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Request models ────────────────────────────────────────────────────────────

class FilterBlock(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    include_match: str = "any"  # "any" | "all"


class FilterConfig(BaseModel):
    modes: FilterBlock = Field(default_factory=FilterBlock)
    main_streets: FilterBlock = Field(default_factory=FilterBlock)


class JourneyRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    max_transfers: int = Field(default=2, ge=0, le=5)
    walking_cutoff: int = Field(default=1000, ge=100, le=5000)
    priority: str = "balanced"
    top_k: int = Field(default=5, ge=1, le=20)
    weights: Optional[dict[str, float]] = None
    filters: Optional[FilterConfig] = None


# ── Response models ───────────────────────────────────────────────────────────

class StopInfo(BaseModel):
    stop_id: str
    name: str
    name_ar: str
    coord: list[float]


class WalkLeg(BaseModel):
    type: str = "walk"
    distance_meters: int
    duration_minutes: int
    polyline: str


class TripLeg(BaseModel):
    type: str = "trip"
    trip_id: str
    trip_ids: list[str]
    mode_en: str
    mode_ar: str
    route_short_name: str
    route_short_name_ar: str
    headsign: str
    headsign_ar: str
    fare: float
    distance_meters: int
    duration_minutes: int
    from_stop: StopInfo = Field(alias="from")
    to_stop: StopInfo = Field(alias="to")
    polyline: str

    model_config = {"populate_by_name": True}


class TransferLeg(BaseModel):
    type: str = "transfer"
    from_trip_id: str
    to_trip_id: str
    from_trip_name: str
    from_trip_name_ar: str
    to_trip_name: str
    to_trip_name_ar: str
    end_stop_id: str
    walking_distance_meters: int
    duration_minutes: int
    polyline: str


class JourneySummary(BaseModel):
    total_time_minutes: int
    walking_distance_meters: int
    transit_distance_meters: int
    total_distance_meters: int
    transfers: int
    cost: float
    modes_en: list[str]
    modes_ar: list[str]
    main_streets_en: list[str]
    main_streets_ar: list[str]


class Journey(BaseModel):
    id: int
    text_summary: str = ""
    text_summary_en: str = ""
    summary: JourneySummary
    legs: list[dict]  # Mixed leg types — kept as dicts for flexibility
    labels: list[str] = Field(default_factory=list)
    labels_ar: list[str] = Field(default_factory=list)
    recommended_for: Optional[str] = None


class JourneyResponse(BaseModel):
    geometry_encoding: str = "polyline5"
    selected_priority: str = "balanced"
    weights_used: dict[str, float] = Field(default_factory=dict)
    num_journeys: int = 0
    journeys: list[dict] = Field(default_factory=list)
    start_trips_found: int = 0
    end_trips_found: int = 0
    total_routes_found: Optional[int] = None
    total_after_dedup: Optional[int] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    graph_nodes: int = 0
    graph_edges: int = 0
    trip_graph_edges: int = 0
    trips_loaded: int = 0

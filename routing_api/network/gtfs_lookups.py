"""
GTFS lookup dictionaries: build from DataFrames or load from pickle cache.

All 13 lookup dicts are bundled into a single GTFSLookups dataclass for
clean dependency injection across the application.
"""
from __future__ import annotations

import os
import pickle
from dataclasses import dataclass, field

import pandas as pd

from routing_api.config import settings

LOOKUP_SCHEMA_VERSION = 3  # bump when cached structure changes


def _parse_pipe_list(value) -> list[str]:
    if pd.isna(value):
        return []
    return [p.strip() for p in str(value).strip().split("|") if p.strip()]


@dataclass
class GTFSLookups:
    """Container for all GTFS lookup dictionaries."""
    trip_to_route: dict = field(default_factory=dict)
    route_to_agency: dict = field(default_factory=dict)
    route_to_short_name: dict = field(default_factory=dict)
    route_to_short_name_ar: dict = field(default_factory=dict)
    trip_to_headsign: dict = field(default_factory=dict)
    trip_to_headsign_ar: dict = field(default_factory=dict)
    stop_to_coords: dict = field(default_factory=dict)
    stop_to_name: dict = field(default_factory=dict)
    stop_to_name_ar: dict = field(default_factory=dict)
    trip_to_shape: dict = field(default_factory=dict)
    shape_points: dict = field(default_factory=dict)
    trip_to_main_streets: dict = field(default_factory=dict)
    trip_to_main_streets_ar: dict = field(default_factory=dict)


def load_gtfs_lookups(
    stops: pd.DataFrame,
    routes: pd.DataFrame,
    trips: pd.DataFrame,
    shapes: pd.DataFrame,
    *,
    force_rebuild: bool | None = None,
) -> GTFSLookups:
    """Build or load all GTFS lookup dictionaries."""
    force = force_rebuild if force_rebuild is not None else settings.force_rebuild_lookups
    cache_path = str(settings.resolve(settings.gtfs_lookup_cache_path))

    lookup_meta = {
        "schema_version": LOOKUP_SCHEMA_VERSION,
        "stops_rows": int(len(stops)),
        "routes_rows": int(len(routes)),
        "trips_rows": int(len(trips)),
        "shapes_rows": int(len(shapes)),
    }

    can_load = False
    if (not force) and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
        can_load = cache.get("_meta") == lookup_meta
    else:
        cache = {}

    if can_load:
        lookups = GTFSLookups(
            trip_to_route=cache["trip_to_route"],
            route_to_agency=cache["route_to_agency"],
            route_to_short_name=cache["route_to_short_name"],
            route_to_short_name_ar=cache["route_to_short_name_ar"],
            trip_to_headsign=cache["trip_to_headsign"],
            trip_to_headsign_ar=cache["trip_to_headsign_ar"],
            stop_to_coords=cache["stop_to_coords"],
            stop_to_name=cache["stop_to_name"],
            stop_to_name_ar=cache["stop_to_name_ar"],
            trip_to_shape=cache["trip_to_shape"],
            shape_points=cache["shape_points"],
            trip_to_main_streets=cache["trip_to_main_streets"],
            trip_to_main_streets_ar=cache["trip_to_main_streets_ar"],
        )
        source = "pickle cache"
    else:
        trip_to_route = trips.set_index("trip_id")["route_id"].to_dict()
        route_to_agency = routes.set_index("route_id")["agency_id"].to_dict()
        route_to_short_name = routes.set_index("route_id")["route_short_name"].to_dict()
        route_to_short_name_ar = (
            routes.set_index("route_id")["route_short_name_ar"].to_dict()
            if "route_short_name_ar" in routes.columns else {}
        )
        trip_to_headsign = trips.set_index("trip_id")["trip_headsign"].to_dict()
        trip_to_headsign_ar = (
            trips.set_index("trip_id")["trip_headsign_ar"].to_dict()
            if "trip_headsign_ar" in trips.columns else {}
        )
        stop_to_coords = stops.set_index("stop_id")[["stop_lat", "stop_lon"]].to_dict("index")
        stop_to_name = stops.set_index("stop_id")["stop_name"].to_dict()
        stop_to_name_ar = (
            stops.set_index("stop_id")["stop_name_ar"].to_dict()
            if "stop_name_ar" in stops.columns else {}
        )
        trip_to_shape = trips.set_index("trip_id")["shape_id"].to_dict()

        shape_pts = {}
        for shape_id, group in shapes.groupby("shape_id"):
            shape_pts[shape_id] = (
                group.sort_values("shape_pt_sequence")[["shape_pt_lat", "shape_pt_lon"]]
                .values.tolist()
            )

        trip_to_main_streets = {}
        trip_to_main_streets_ar = {}
        if "main_streets" in trips.columns:
            trip_to_main_streets = {
                r.trip_id: _parse_pipe_list(r.main_streets)
                for r in trips[["trip_id", "main_streets"]].itertuples(index=False)
            }
        if "main_streets_ar" in trips.columns:
            trip_to_main_streets_ar = {
                r.trip_id: _parse_pipe_list(r.main_streets_ar)
                for r in trips[["trip_id", "main_streets_ar"]].itertuples(index=False)
            }

        lookups = GTFSLookups(
            trip_to_route=trip_to_route,
            route_to_agency=route_to_agency,
            route_to_short_name=route_to_short_name,
            route_to_short_name_ar=route_to_short_name_ar,
            trip_to_headsign=trip_to_headsign,
            trip_to_headsign_ar=trip_to_headsign_ar,
            stop_to_coords=stop_to_coords,
            stop_to_name=stop_to_name,
            stop_to_name_ar=stop_to_name_ar,
            trip_to_shape=trip_to_shape,
            shape_points=shape_pts,
            trip_to_main_streets=trip_to_main_streets,
            trip_to_main_streets_ar=trip_to_main_streets_ar,
        )

        # Save cache
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            cache_data = {"_meta": lookup_meta}
            for fld in lookups.__dataclass_fields__:
                cache_data[fld] = getattr(lookups, fld)
            pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        source = "fresh build"

    print(f"[gtfs_lookups] Source: {source}")
    print(f"[gtfs_lookups] trip_to_route: {len(lookups.trip_to_route)} | "
          f"stop_to_coords: {len(lookups.stop_to_coords)} | "
          f"shapes: {len(lookups.shape_points)}")
    return lookups

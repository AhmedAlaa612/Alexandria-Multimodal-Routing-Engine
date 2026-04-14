"""
Core update logic: call Google Maps for each trip → build new prefixtimes.json.
"""
from __future__ import annotations

import json
import os
import time
import threading
from datetime import datetime, timezone

import pandas as pd
import urllib.request

from traffic_updater.config import settings
from traffic_updater.gmaps.client import get_directions


# ── Module state ──────────────────────────────────────────────────────────────
_lock = threading.Lock()
_is_running = False
_last_update: str | None = None
_trips_in_data = 0


def get_status() -> dict:
    """Current update status."""
    return {
        "status": "running" if _is_running else "idle",
        "last_update": _last_update,
        "trips_in_data": _trips_in_data,
        "is_running": _is_running,
    }


def _load_gtfs_stop_coords() -> dict:
    """Load stop_id → (lat, lon) from GTFS."""
    stops_df = pd.read_csv(str(settings.resolve(settings.gtfs_path)) + "/stops.txt")
    return {
        str(row.stop_id): (float(row.stop_lat), float(row.stop_lon))
        for row in stops_df.itertuples(index=False)
    }


def _load_stop_times() -> pd.DataFrame:
    """Load and sort stop_times."""
    path = str(settings.resolve(settings.gtfs_path)) + "/stop_times.txt"
    df = pd.read_csv(path)
    df["stop_id"] = df["stop_id"].astype(str)
    df["trip_id"] = df["trip_id"].astype(str)
    return df.sort_values(["trip_id", "stop_sequence"])


def _notify_routing_api():
    """POST to the routing API to hot-reload prefixtimes."""
    try:
        url = f"{settings.routing_api_url}/api/v1/admin/reload-times"
        req = urllib.request.Request(url, method="POST", data=b"")
        req.add_header("x-admin-key", settings.routing_admin_key)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[updater] Routing API notified: {resp.status}")
    except Exception as e:
        print(f"[updater] Failed to notify routing API: {e}")


def _get_trip_times_chunked(coords: list[tuple[float, float]], valid_stop_ids: list[str]) -> dict:
    """Gets travel times for a trip, chunking requests if stops exceed Google Maps limits (e.g. 20)."""
    CHUNK_MAX = 20
    trip_entry = {valid_stop_ids[0]: 0}
    cum_time = 0
    
    # Step by CHUNK_MAX - 1 so the last stop of chunk N is the first stop of chunk N+1
    for i in range(0, len(coords) - 1, CHUNK_MAX - 1):
        chunk_coords = coords[i:i + CHUNK_MAX]
        chunk_stop_ids = valid_stop_ids[i:i + CHUNK_MAX]
        
        if len(chunk_coords) < 2:
            break
            
        result = get_directions(
            chunk_coords,
            language=settings.gmaps_language,
            country=settings.gmaps_country,
        )
        legs = result.get("legs", [])
        
        if not legs:
            raise ValueError(f"Google Maps returned zero legs for chunk {i}")
                
        for leg_idx, leg in enumerate(legs):
            if leg_idx + 1 < len(chunk_stop_ids):
                cum_time += leg["duration_seconds"]
                trip_entry[chunk_stop_ids[leg_idx + 1]] = cum_time
                
        # Sleep between chunks of the SAME trip to avoid getting blocked
        if i + CHUNK_MAX - 1 < len(coords) - 1:
            time.sleep(settings.gmaps_request_delay)
            
    return trip_entry


def update_all_trips(*, notify: bool = True) -> dict:
    """
    Full update cycle: query Google Maps for every trip and rewrite prefixtimes.json.

    Returns summary dict with counts.
    """
    global _is_running, _last_update, _trips_in_data

    with _lock:
        if _is_running:
            return {"status": "error", "trips_updated": 0, "trips_failed": 0,
                    "message": "Update already in progress"}
        _is_running = True

    try:
        stop_coords = _load_gtfs_stop_coords()
        stop_times = _load_stop_times()

        # Load existing data as base
        times_path = str(settings.resolve(settings.prefix_times_path))
        if os.path.exists(times_path):
            with open(times_path) as f:
                prefix_times = json.load(f)
        else:
            prefix_times = {}

        updated = 0
        failed = 0

        for trip_id, group in stop_times.groupby("trip_id"):
            ordered = group.sort_values("stop_sequence")
            stops_list = ordered["stop_id"].tolist()

            # Build coordinate list for this trip's stops
            coords = []
            valid_stop_ids = []
            for sid in stops_list:
                c = stop_coords.get(sid)
                if c:
                    coords.append(c)
                    valid_stop_ids.append(sid)

            if len(coords) < 2:
                continue

            try:
                trip_entry = _get_trip_times_chunked(coords, valid_stop_ids)
                prefix_times[trip_id] = trip_entry
                updated += 1

            except Exception as e:
                print(f"[updater] Failed trip {trip_id}: {e}")
                failed += 1

            # Rate limiting
            time.sleep(settings.gmaps_request_delay)

        # Atomic write
        tmp_path = times_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(prefix_times, f, indent=2)
        os.replace(tmp_path, times_path)

        _trips_in_data = len(prefix_times)
        _last_update = datetime.now(timezone.utc).isoformat()

        if notify:
            _notify_routing_api()

        return {"status": "ok", "trips_updated": updated, "trips_failed": failed,
                "message": f"Updated {updated} trips, {failed} failed"}

    finally:
        with _lock:
            _is_running = False


def update_single_trip(trip_id: str, *, notify: bool = True) -> dict:
    """Update travel times for a single trip."""
    global _last_update, _trips_in_data

    stop_coords = _load_gtfs_stop_coords()
    stop_times = _load_stop_times()

    trip_stops = stop_times[stop_times["trip_id"] == trip_id].sort_values("stop_sequence")
    if trip_stops.empty:
        return {"status": "error", "trips_updated": 0, "trips_failed": 0,
                "message": f"Trip {trip_id} not found in stop_times"}

    stops_list = trip_stops["stop_id"].tolist()
    coords = []
    valid_stop_ids = []
    for sid in stops_list:
        c = stop_coords.get(sid)
        if c:
            coords.append(c)
            valid_stop_ids.append(sid)

    if len(coords) < 2:
        return {"status": "error", "trips_updated": 0, "trips_failed": 0,
                "message": "Not enough stops with valid coordinates"}

    try:
        trip_entry = _get_trip_times_chunked(coords, valid_stop_ids)
    except Exception as e:
        return {"status": "error", "trips_updated": 0, "trips_failed": 1,
                "message": f"Google Maps request failed: {e}"}

    # Read-modify-write
    times_path = str(settings.resolve(settings.prefix_times_path))
    with open(times_path) as f:
        prefix_times = json.load(f)
    prefix_times[trip_id] = trip_entry
    tmp_path = times_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(prefix_times, f, indent=2)
    os.replace(tmp_path, times_path)

    _trips_in_data = len(prefix_times)
    _last_update = datetime.now(timezone.utc).isoformat()

    if notify:
        _notify_routing_api()

    return {"status": "ok", "trips_updated": 1, "trips_failed": 0,
            "message": f"Updated trip {trip_id}"}

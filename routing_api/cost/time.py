"""
Travel time model: prefix-sum travel times per trip.

Supports hot-reload so the traffic updater can push new data without restarting.
"""

import json
import threading

from routing_api.config import settings

# Module-level state (loaded at startup, hot-reloadable)
_traffic_data: dict = {}
_lock = threading.Lock()


def load_prefix_times() -> None:
    """Load prefixtimes.json into module state."""
    global _traffic_data
    path = str(settings.resolve(settings.prefix_times_path))
    with open(path) as f:
        data = json.load(f)
    with _lock:
        _traffic_data = data
    print(f"[time] Loaded prefix times for {len(_traffic_data)} trips")


def reload_prefix_times() -> int:
    """
    Hot-reload prefixtimes.json from disk.

    Called by the admin endpoint after the traffic updater writes new data.

    Returns
    -------
    int
        Number of trips loaded.
    """
    load_prefix_times()
    return len(_traffic_data)


def get_transport_time(trip_id: str, start_stop: str, end_stop: str) -> float:
    """Travel time in seconds between two stops for a trip."""
    with _lock:
        t = _traffic_data[trip_id]
    return float(t[str(end_stop)]) - float(t[str(start_stop)])

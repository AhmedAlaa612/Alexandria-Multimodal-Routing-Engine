"""
Distance model: prefix-sum distances per trip.
"""

import json

from routing_api.config import settings

# Module-level state (loaded once at startup)
_distance_data: dict = {}


def load_prefix_distances() -> None:
    """Load prefixdistances.json into module state."""
    global _distance_data
    path = str(settings.resolve(settings.prefix_distances_path))
    with open(path) as f:
        _distance_data = json.load(f)
    print(f"[distance] Loaded prefix distances for {len(_distance_data)} trips")


def get_distance_km(trip_id: str, start_stop: str, end_stop: str) -> float:
    """Segment distance in km between two stops using prefix distances."""
    trip_data = _distance_data.get(trip_id, {})
    if not isinstance(trip_data, dict):
        return 0.0
    return abs(trip_data.get(str(end_stop), 0) - trip_data.get(str(start_stop), 0)) / 1000

"""
Filter resolver: pre-compute excluded trip IDs from user-facing filter config.

Only exclusion filters are resolved here — include-side filters are
journey-level constraints checked after routing (see inclusions.py).
"""
from __future__ import annotations

from routing_api.network.gtfs_lookups import GTFSLookups


def build_excluded_trips(lookups: GTFSLookups, filters: dict | None = None) -> set:
    """
    exclusion filters are applied here
    
    - filters.modes.exclude        : agency_id strings to block entirely
    - filters.main_streets.exclude : street name strings to block entirely
    """
    filters = filters or {}

    mode_exc = set(filters.get("modes", {}).get("exclude", []))
    street_exc = set(filters.get("main_streets", {}).get("exclude", []))

    if not mode_exc and not street_exc:
        return set()

    excluded = set()
    for trip_id, route_id in lookups.trip_to_route.items():
        if mode_exc:
            agency = lookups.route_to_agency.get(route_id, "")
            if agency in mode_exc:
                excluded.add(trip_id)
                continue

        if street_exc:
            streets = set(lookups.trip_to_main_streets.get(trip_id, []))
            if streets & street_exc:
                excluded.add(trip_id)

    return excluded

"""
Filter resolver: pre-compute excluded trip IDs from user-facing filter config.
"""
from __future__ import annotations

from routing_api.network.gtfs_lookups import GTFSLookups


def build_excluded_trips(lookups: GTFSLookups, filters: dict | None = None) -> set:
    """
    Pre-resolve filters into a set of trip_ids to exclude before BFS.

    - filters.modes.include/exclude : agency_id strings
    - filters.main_streets.include/exclude : English street name strings
    """
    filters = filters or {}

    mode_cfg = filters.get("modes", {"include": [], "exclude": [], "include_match": "any"})
    street_cfg = filters.get("main_streets", {"include": [], "exclude": [], "include_match": "any"})

    mode_inc = set(mode_cfg.get("include", []))
    mode_exc = set(mode_cfg.get("exclude", []))
    street_inc = set(street_cfg.get("include", []))
    street_exc = set(street_cfg.get("exclude", []))
    street_match = street_cfg.get("include_match", "any")

    no_mode_filter = not mode_inc and not mode_exc
    no_street_filter = not street_inc and not street_exc
    if no_mode_filter and no_street_filter:
        return set()

    excluded = set()
    for trip_id, route_id in lookups.trip_to_route.items():
        # ── mode / agency check ──
        if not no_mode_filter:
            agency = lookups.route_to_agency.get(route_id, "")
            if agency in mode_exc:
                excluded.add(trip_id)
                continue
            if mode_inc and agency not in mode_inc:
                excluded.add(trip_id)
                continue

        # ── street check ──
        if not no_street_filter:
            streets = set(lookups.trip_to_main_streets.get(trip_id, []))
            if street_exc and streets & street_exc:
                excluded.add(trip_id)
                continue
            if street_inc:
                if street_match == "all" and not street_inc <= streets:
                    excluded.add(trip_id)
                    continue
                if street_match != "all" and not streets & street_inc:
                    excluded.add(trip_id)
                    continue

    return excluded

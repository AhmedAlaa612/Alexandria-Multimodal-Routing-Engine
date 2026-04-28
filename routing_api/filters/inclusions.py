"""
Post-routing include filter: check assembled journeys against include constraints.

Called after find_journeys_pareto, before dedup/rank/top_k, so the full pool
of candidate journeys is available and include filters can't silently starve
the top_k result set.

Raw pareto results have the shape:
    (trip_path, cost_vector, cost_details)

Where:
    trip_path   : list[str]  — ordered trip_ids in the journey
    cost_vector : tuple      — (transfers, fare, time, walk)
    cost_details: list[dict] — per-leg dicts with keys: type, trip_id, agency_id, ...
"""
from __future__ import annotations


def journey_satisfies_includes(result: tuple, filters: dict, lookups) -> bool:
    """
    Return True if the journey meets all include constraints.

    Checks across every leg of the journey so that a mode/street present
    in any leg (including transfers) satisfies the filter.

    Parameters
    ----------
    result  : single item from find_journeys_pareto output
    filters : filters dict (already model_dump'd)
    lookups : GTFSLookups instance
    """
    mode_cfg = filters.get("modes", {})
    street_cfg = filters.get("main_streets", {})

    mode_inc = set(mode_cfg.get("include", []))
    street_inc = set(street_cfg.get("include", []))
    street_match = street_cfg.get("include_match", "any")

    # Nothing to include-filter — pass through
    if not mode_inc and not street_inc:
        return True

    trip_path, _cost_vector, _cost_details = result

    # Collect agencies and streets across all trips in this journey
    journey_agencies: set[str] = set()
    journey_streets: set[str] = set()

    for trip_id in trip_path:
        route_id = lookups.trip_to_route.get(trip_id)
        if route_id:
            agency = lookups.route_to_agency.get(route_id, "")
            if agency:
                journey_agencies.add(agency)
        journey_streets.update(lookups.trip_to_main_streets.get(trip_id, []))

    # Mode include check — at least one leg must use an included agency
    if mode_inc and not (journey_agencies & mode_inc):
        return False

    # Street include check
    if street_inc:
        if street_match == "all" and not street_inc <= journey_streets:
            return False
        if street_match != "all" and not (journey_streets & street_inc):
            return False

    return True


def apply_include_filters(routing_results: list, filters: dict | None, lookups) -> list:
    """
    Filter the raw pareto results list to only journeys satisfying include constraints.

    Returns the full list unchanged if no include filters are set.
    """
    if not filters:
        return routing_results

    mode_inc = filters.get("modes", {}).get("include", [])
    street_inc = filters.get("main_streets", {}).get("include", [])
    if not mode_inc and not street_inc:
        return routing_results

    return [r for r in routing_results if journey_satisfies_includes(r, filters, lookups)]

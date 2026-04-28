"""
Top-level journey pipeline: coordinates → enriched frontend-ready journeys.

This is the single file that wires all domain modules together.
"""

import osmnx as ox

from routing_api.routing.explorer import explore_trips
from routing_api.routing.pareto import find_journeys_pareto
from routing_api.routing.dedup import deduplicate_routing_results
from routing_api.routing.walking import build_walking_journey
from routing_api.ranking.profiles import resolve_ranking_weights
from routing_api.ranking.ranker import rank_routing_results
from routing_api.presentation.enricher import enrich_journey_results
from routing_api.presentation.labels import add_journey_labels
from routing_api.filters.exclusions import build_excluded_trips
from routing_api.filters.inclusions import apply_include_filters


def find_journeys(
    start_lat, start_lon, end_lat, end_lon,
    *,
    graph,
    trip_graph,
    pathway_metadata,
    lookups,
    max_transfers=2,
    walking_cutoff=1000,
    weights=None,
    priority="balanced",
    filters=None,
    top_k=5,
):
    """
    Complete pipeline: coordinates → enriched frontend-ready journeys.

    Pipeline steps:
        validate → nearest nodes → walking check → explore_trips (start+end)
        → build excluded_trips (exclude filters, pre-BFS)
        → pareto BFS
        → apply_include_filters (include filters, post-BFS, pre-dedup — full pool)
        → dedup → rank → enrich → label
    """
    ranking_weights, resolved_priority = resolve_ranking_weights(
        priority=priority, custom_weights=weights,
    )

    try:
        start_lat = float(start_lat)
        start_lon = float(start_lon)
        end_lat = float(end_lat)
        end_lon = float(end_lon)
    except (TypeError, ValueError) as e:
        raise ValueError("start/end coordinates must be numeric values") from e

    if any(v != v for v in (start_lat, start_lon, end_lat, end_lon)):
        raise ValueError("start/end coordinates cannot be NaN")

    start_node = ox.distance.nearest_nodes(graph, X=start_lon, Y=start_lat)
    end_node = ox.distance.nearest_nodes(graph, X=end_lon, Y=end_lat)

    walking_journey = build_walking_journey(graph, start_node, end_node, walking_cutoff)
    start_trips = explore_trips(graph, start_node, cutoff=walking_cutoff)
    target_trips = explore_trips(graph, end_node, cutoff=walking_cutoff)

    def early_return(error=None):
        journeys = [walking_journey] if walking_journey else []
        add_journey_labels(journeys, resolved_priority)
        return {
            "geometry_encoding": "polyline5",
            "selected_priority": resolved_priority,
            "weights_used": ranking_weights,
            "num_journeys": len(journeys),
            "journeys": journeys,
            "start_trips_found": len(start_trips),
            "end_trips_found": len(target_trips),
            "error": error,
        }

    if not start_trips:
        return early_return(
            None if walking_journey
            else f"No transit trips found within {walking_cutoff}m of start location"
        )
    if not target_trips:
        return early_return(
            None if walking_journey
            else f"No transit trips found within {walking_cutoff}m of end location"
        )

    # Convert FilterConfig to dict if it's a Pydantic model
    filters_dict = None
    if filters is not None:
        if hasattr(filters, "model_dump"):
            filters_dict = filters.model_dump()
        else:
            filters_dict = filters

    # ── Pre-BFS: exclude filters only ────────────────────────────────────────
    # Drops individual trips that should never appear (exclude-side only).
    excluded_trips = build_excluded_trips(lookups, filters=filters_dict)
    routing_results = find_journeys_pareto(
        trip_graph, start_trips, target_trips, max_transfers, excluded_trips,
    )
    if not routing_results:
        return early_return(
            None if walking_journey else "No valid journeys found between the locations"
        )

    # ── Post-BFS, pre-dedup: include filters ─────────────────────────────────
    # Checks the full pool of candidate journeys so that include filters can't
    # silently starve the top_k result set. A journey satisfies an include if
    # *any* of its legs (including transfers) uses the requested mode/street.
    routing_results = apply_include_filters(routing_results, filters_dict, lookups)
    if not routing_results:
        return early_return(
            None if walking_journey else "No journeys matched the requested filters"
        )

    deduped_results = deduplicate_routing_results(routing_results)
    ranked_results = rank_routing_results(deduped_results, ranking_weights, top_n=top_k)
    enriched = enrich_journey_results(
        ranked_results, start_trips, target_trips,
        lookups, pathway_metadata, top_k,
    )
    journeys = enriched["journeys"]

    if walking_journey:
        journeys.insert(0, walking_journey)

    for i, j in enumerate(journeys):
        j["id"] = i + 1
    add_journey_labels(journeys, resolved_priority)

    return {
        "geometry_encoding": "polyline5",
        "selected_priority": resolved_priority,
        "weights_used": ranking_weights,
        "num_journeys": len(journeys),
        "journeys": journeys,
        "start_trips_found": len(start_trips),
        "end_trips_found": len(target_trips),
        "total_routes_found": len(routing_results),
        "total_after_dedup": len(deduped_results),
        "error": None,
    }

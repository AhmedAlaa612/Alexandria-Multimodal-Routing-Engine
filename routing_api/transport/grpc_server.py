"""
gRPC server for the routing service.

Runs in a background thread alongside the FastAPI process.
Uses grpcio reflection so clients can discover the service schema.
"""
from __future__ import annotations

import asyncio
import threading
from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection

from routing_api.config import settings
from routing_api.pipeline import find_journeys


# ── Protobuf stubs ────────────────────────────────────────────────────────────
# These are generated from routing.proto.  We generate them at build time with:
#   python -m grpc_tools.protoc -I routing_api/proto \
#       --python_out=routing_api/proto --grpc_python_out=routing_api/proto \
#       routing_api/proto/routing.proto
#
# If the generated files don't exist yet, the gRPC server falls back to
# serving only via REST (FastAPI).

_grpc_available = False
_pb2 = None
_pb2_grpc = None

try:
    from routing_api.proto import routing_pb2 as _pb2
    from routing_api.proto import routing_pb2_grpc as _pb2_grpc
    _grpc_available = True
except ImportError:
    pass


def _dict_to_journey_pb(j_dict):
    """Convert a journey dict to a protobuf Journey message."""
    summary_dict = j_dict.get("summary", {})
    summary = _pb2.JourneySummary(
        total_time_minutes=summary_dict.get("total_time_minutes", 0),
        walking_distance_meters=summary_dict.get("walking_distance_meters", 0),
        transit_distance_meters=summary_dict.get("transit_distance_meters", 0),
        total_distance_meters=summary_dict.get("total_distance_meters", 0),
        transfers=summary_dict.get("transfers", 0),
        cost=summary_dict.get("cost", 0),
        modes_en=summary_dict.get("modes_en", []),
        modes_ar=summary_dict.get("modes_ar", []),
        main_streets_en=summary_dict.get("main_streets_en", []),
        main_streets_ar=summary_dict.get("main_streets_ar", []),
    )

    legs = []
    for leg_d in j_dict.get("legs", []):
        leg_kwargs = {
            "type": leg_d.get("type", ""),
            "distance_meters": leg_d.get("distance_meters", 0),
            "duration_minutes": leg_d.get("duration_minutes", 0),
            "polyline": leg_d.get("polyline", ""),
        }
        if leg_d["type"] == "trip":
            from_d = leg_d.get("from", {})
            to_d = leg_d.get("to", {})
            leg_kwargs.update(
                trip_id=leg_d.get("trip_id", ""),
                trip_ids=leg_d.get("trip_ids", []),
                mode_en=leg_d.get("mode_en", ""),
                mode_ar=leg_d.get("mode_ar", ""),
                route_short_name=leg_d.get("route_short_name", ""),
                route_short_name_ar=leg_d.get("route_short_name_ar", ""),
                headsign=leg_d.get("headsign", ""),
                headsign_ar=leg_d.get("headsign_ar", ""),
                fare=leg_d.get("fare", 0),
                from_stop=_pb2.StopInfo(
                    stop_id=from_d.get("stop_id", ""),
                    name=from_d.get("name", ""),
                    name_ar=from_d.get("name_ar", ""),
                    coord=from_d.get("coord", []),
                ),
                to_stop=_pb2.StopInfo(
                    stop_id=to_d.get("stop_id", ""),
                    name=to_d.get("name", ""),
                    name_ar=to_d.get("name_ar", ""),
                    coord=to_d.get("coord", []),
                ),
            )
        elif leg_d["type"] == "transfer":
            leg_kwargs.update(
                from_trip_id=leg_d.get("from_trip_id", ""),
                to_trip_id=leg_d.get("to_trip_id", ""),
                from_trip_name=leg_d.get("from_trip_name", ""),
                from_trip_name_ar=leg_d.get("from_trip_name_ar", ""),
                to_trip_name=leg_d.get("to_trip_name", ""),
                to_trip_name_ar=leg_d.get("to_trip_name_ar", ""),
                end_stop_id=leg_d.get("end_stop_id", ""),
                walking_distance_meters=leg_d.get("walking_distance_meters", 0),
            )
        legs.append(_pb2.Leg(**leg_kwargs))

    return _pb2.Journey(
        id=j_dict.get("id", 0),
        text_summary=j_dict.get("text_summary", ""),
        text_summary_en=j_dict.get("text_summary_en", ""),
        summary=summary,
        legs=legs,
        labels=j_dict.get("labels", []),
        labels_ar=j_dict.get("labels_ar", []),
        recommended_for=j_dict.get("recommended_for", ""),
    )


class RoutingServicer(_pb2_grpc.RoutingServiceServicer if _grpc_available else object):
    """gRPC servicer for RoutingService."""

    def __init__(self, app_state: dict):
        self._state = app_state

    def FindJourneys(self, request, context):
        filters_dict = None
        if request.HasField("filters"):
            filters_dict = {
                "modes": {
                    "include": list(request.filters.modes.include),
                    "exclude": list(request.filters.modes.exclude),
                    "include_match": request.filters.modes.include_match or "any",
                },
                "main_streets": {
                    "include": list(request.filters.main_streets.include),
                    "exclude": list(request.filters.main_streets.exclude),
                    "include_match": request.filters.main_streets.include_match or "any",
                },
            }

        weights_dict = dict(request.weights) if request.weights else None

        try:
            result = find_journeys(
                request.start_lat, request.start_lon,
                request.end_lat, request.end_lon,
                graph=self._state["graph"],
                trip_graph=self._state["trip_graph"],
                pathway_metadata=self._state["pathway_metadata"],
                lookups=self._state["lookups"],
                max_transfers=request.max_transfers or 2,
                walking_cutoff=request.walking_cutoff or 1000,
                weights=weights_dict,
                priority=request.priority or "balanced",
                filters=filters_dict,
                top_k=request.top_k or 5,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return _pb2.JourneyResponse()

        journeys_pb = [_dict_to_journey_pb(j) for j in result.get("journeys", [])]

        return _pb2.JourneyResponse(
            geometry_encoding=result.get("geometry_encoding", "polyline5"),
            selected_priority=result.get("selected_priority", "balanced"),
            weights_used=result.get("weights_used", {}),
            num_journeys=result.get("num_journeys", 0),
            journeys=journeys_pb,
            start_trips_found=result.get("start_trips_found", 0),
            end_trips_found=result.get("end_trips_found", 0),
            total_routes_found=result.get("total_routes_found", 0),
            total_after_dedup=result.get("total_after_dedup", 0),
            error=result.get("error") or "",
        )

    def HealthCheck(self, request, context):
        g = self._state.get("graph")
        tg = self._state.get("trip_graph", {})
        lookups = self._state.get("lookups")
        return _pb2.HealthResponse(
            status="ok",
            graph_nodes=g.number_of_nodes() if g else 0,
            graph_edges=g.number_of_edges() if g else 0,
            trip_graph_edges=sum(len(v) for v in tg.values()) if tg else 0,
            trips_loaded=len(lookups.trip_to_route) if lookups else 0,
        )


def start_grpc_server(app_state: dict, port: int | None = None):
    """
    Start the gRPC server in a daemon thread.

    Returns None if protobuf stubs haven't been compiled yet.
    """
    if not _grpc_available:
        print("[grpc] Protobuf stubs not found - gRPC disabled. "
              "Run `python -m grpc_tools.protoc ...` to enable.")
        return None

    port = port or settings.grpc_port
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    _pb2_grpc.add_RoutingServiceServicer_to_server(
        RoutingServicer(app_state), server,
    )

    # Enable reflection
    service_names = (
        _pb2.DESCRIPTOR.services_by_name["RoutingService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[grpc] RoutingService listening on port {port}")
    return server

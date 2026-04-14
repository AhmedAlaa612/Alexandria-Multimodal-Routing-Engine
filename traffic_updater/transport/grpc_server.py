"""
gRPC server for the traffic updater service.
"""
from __future__ import annotations

from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection

from traffic_updater.config import settings
from traffic_updater.updater.prefix_times import (
    update_all_trips, update_single_trip, get_status,
)
from traffic_updater.streets.traffic import (
    get_street_traffic, get_available_streets,
)

_grpc_available = False
_pb2 = None
_pb2_grpc = None

try:
    from traffic_updater.proto import traffic_pb2 as _pb2
    from traffic_updater.proto import traffic_pb2_grpc as _pb2_grpc
    _grpc_available = True
except ImportError:
    pass


class TrafficUpdateServicer(_pb2_grpc.TrafficUpdateServiceServicer if _grpc_available else object):

    def TriggerUpdate(self, request, context):
        result = update_all_trips(notify=request.notify_routing_api)
        return _pb2.UpdateResponse(
            status=result["status"],
            trips_updated=result["trips_updated"],
            trips_failed=result["trips_failed"],
            message=result["message"],
        )

    def GetStatus(self, request, context):
        s = get_status()
        return _pb2.StatusResponse(
            status=s["status"],
            last_update=s.get("last_update") or "",
            trips_in_data=s["trips_in_data"],
            is_running=s["is_running"],
        )

    def UpdateTrip(self, request, context):
        result = update_single_trip(
            request.trip_id, notify=request.notify_routing_api,
        )
        return _pb2.UpdateResponse(
            status=result["status"],
            trips_updated=result["trips_updated"],
            trips_failed=result["trips_failed"],
            message=result["message"],
        )

    def StreetTraffic(self, request, context):
        result = get_street_traffic(
            street_name=request.name,
            language=request.language or "en",
            max_waypoints=request.max_waypoints or 20,
        )
        legs = [
            _pb2.StreetTrafficLeg(
                distance_m=leg.get("distance_m", 0),
                distance_text=leg.get("distance_text", ""),
                duration_seconds=leg.get("duration_seconds", 0),
                duration_text=leg.get("duration_text", ""),
            ) for leg in result.get("legs", [])
        ]
        routes = [
            _pb2.StreetTrafficRoute(
                label=r.get("label", ""),
                distance_m=r.get("distance_m", 0),
                distance_text=r.get("distance_text", ""),
                duration_seconds=r.get("duration_seconds", 0),
                duration_text=r.get("duration_text", ""),
            ) for r in result.get("routes", [])
        ]
        return _pb2.StreetTrafficResponse(
            street=result.get("street", ""),
            street_ar=result.get("street_ar", ""),
            segments=result.get("segments", 0),
            waypoints_used=result.get("waypoints_used", 0),
            total_distance_km=result.get("total_distance_km", 0),
            total_duration_min=result.get("total_duration_min", 0),
            legs=legs,
            routes=routes,
            error=result.get("error") or "",
        )

    def ListStreets(self, request, context):
        streets_raw = get_available_streets()
        streets = [
            _pb2.StreetInfo(
                name=s["name"],
                name_ar=s.get("name_ar", ""),
                aliases=s.get("aliases", []),
                segments=s.get("segments", 0),
                total_length_km=s.get("total_length_km", 0),
            ) for s in streets_raw
        ]
        return _pb2.StreetListResponse(count=len(streets), streets=streets)


def start_grpc_server(port: int | None = None):
    """Start the traffic updater gRPC server in a daemon thread."""
    if not _grpc_available:
        print("[grpc] Protobuf stubs not found - gRPC disabled.")
        return None

    port = port or settings.grpc_port
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    _pb2_grpc.add_TrafficUpdateServiceServicer_to_server(
        TrafficUpdateServicer(), server,
    )

    service_names = (
        _pb2.DESCRIPTOR.services_by_name["TrafficUpdateService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[grpc] TrafficUpdateService listening on port {port}")
    return server

"""
gRPC server for the DB Tools service.
"""
from __future__ import annotations

from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection

from db_tools.config import settings
from db_tools.db.queries import get_nearby_trips
from db_tools.db.pool import get_pool

_grpc_available = False
_pb2 = None
_pb2_grpc = None

try:
    from db_tools.proto import db_tools_pb2 as _pb2
    from db_tools.proto import db_tools_pb2_grpc as _pb2_grpc
    _grpc_available = True
except ImportError:
    pass


class DbToolsServicer(_pb2_grpc.DbToolsServiceServicer if _grpc_available else object):

    def NearbyTrips(self, request, context):
        try:
            rows = get_nearby_trips(
                lat=request.lat,
                lon=request.lon,
                radius_m=request.radius_m or 1000.0,
                starts=request.starts,
                epsg=request.epsg or 32636,
            )
            trip_results = []
            for r in rows:
                trip_results.append(_pb2.NearbyTripResult(
                    trip_id=str(r.get("trip_id", "")),
                    route_id=str(r.get("route_id", "")),
                    trip_headsign=str(r.get("trip_headsign", "") or ""),
                    trip_headsign_ar=str(r.get("trip_headsign_ar", "") or ""),
                    direction_id=int(r.get("direction_id", 0) or 0),
                    route_short_name=str(r.get("route_short_name", "") or ""),
                    route_short_name_ar=str(r.get("route_short_name_ar", "") or ""),
                    route_name=str(r.get("route_name", "") or ""),
                    route_name_ar=str(r.get("route_name_ar", "") or ""),
                    distance_m=float(r.get("distance_m", 0) or 0),
                    closest_stop_id=str(r.get("closest_stop_id", "") or ""),
                    closest_stop_name=str(r.get("closest_stop_name", "") or ""),
                    closest_stop_name_ar=str(r.get("closest_stop_name_ar", "") or ""),
                    closest_stop_lat=float(r.get("closest_stop_lat", 0) or 0),
                    closest_stop_lon=float(r.get("closest_stop_lon", 0) or 0),
                    closest_stop_sequence=int(r.get("closest_stop_sequence", 0) or 0),
                ))
            return _pb2.NearbyTripsResponse(
                lat=request.lat,
                lon=request.lon,
                radius_m=request.radius_m or 1000.0,
                starts=request.starts,
                epsg=request.epsg or 32636,
                count=len(trip_results),
                trips=trip_results,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return _pb2.NearbyTripsResponse()

    def HealthCheck(self, request, context):
        try:
            pool = get_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return _pb2.HealthResponse(status="ok", db_connected=True)
            finally:
                pool.putconn(conn)
        except Exception:
            return _pb2.HealthResponse(status="degraded", db_connected=False)


def start_grpc_server(port: int | None = None):
    """Start the DB Tools gRPC server in a daemon thread."""
    if not _grpc_available:
        print("[grpc] Protobuf stubs not found - gRPC disabled.")
        return None

    port = port or settings.grpc_port
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    _pb2_grpc.add_DbToolsServiceServicer_to_server(DbToolsServicer(), server)

    service_names = (
        _pb2.DESCRIPTOR.services_by_name["DbToolsService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[grpc] DbToolsService listening on port {port}")
    return server

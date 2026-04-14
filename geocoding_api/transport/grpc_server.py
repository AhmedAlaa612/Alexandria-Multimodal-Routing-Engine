"""
gRPC server for the Geocoding service.
"""
from __future__ import annotations

from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection

from geocoding_api.config import settings
from geocoding_api.geocoder.forward import geocode

_grpc_available = False
_pb2 = None
_pb2_grpc = None

try:
    from geocoding_api.proto import geocoding_pb2 as _pb2
    from geocoding_api.proto import geocoding_pb2_grpc as _pb2_grpc
    _grpc_available = True
except ImportError:
    pass


class GeocodingServicer(_pb2_grpc.GeocodingServiceServicer if _grpc_available else object):

    def Geocode(self, request, context):
        try:
            user_lat = request.user_lat if request.user_lat != 0 else None
            user_lng = request.user_lng if request.user_lng != 0 else None

            raw = geocode(
                address=request.address,
                language=request.language or "en",
                bias=request.bias,
                user_lat=user_lat,
                user_lng=user_lng,
            )

            results = [
                _pb2.GeocodeResult(
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    formatted_address=r["formatted_address"],
                )
                for r in raw
            ]

            if not results:
                return _pb2.GeocodeResponse(
                    success=False,
                    query=request.address,
                    language=request.language or "en",
                    bias=request.bias,
                    count=0,
                    error=f"No results found for: \"{request.address}\"",
                )

            return _pb2.GeocodeResponse(
                success=True,
                query=request.address,
                language=request.language or "en",
                bias=request.bias,
                count=len(results),
                results=results,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return _pb2.GeocodeResponse()

    def HealthCheck(self, request, context):
        return _pb2.HealthResponse(status="ok")


def start_grpc_server(port: int | None = None):
    """Start the Geocoding gRPC server in a daemon thread."""
    if not _grpc_available:
        print("[grpc] Protobuf stubs not found - gRPC disabled.")
        return None

    port = port or settings.grpc_port
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    _pb2_grpc.add_GeocodingServiceServicer_to_server(GeocodingServicer(), server)

    service_names = (
        _pb2.DESCRIPTOR.services_by_name["GeocodingService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[grpc] GeocodingService listening on port {port}")
    return server

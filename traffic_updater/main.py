"""
Traffic Updater — FastAPI application entrypoint.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from traffic_updater.config import settings
from traffic_updater.transport.grpc_server import start_grpc_server

_grpc_server = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _grpc_server
    _grpc_server = start_grpc_server()
    print(f"[traffic-updater] REST listening on port {settings.rest_port}")
    yield
    if _grpc_server:
        _grpc_server.stop(grace=5)
        print("[shutdown] gRPC server stopped")


app = FastAPI(
    title="Traffic Updater API",
    description="Hourly travel-time update service using Google Maps traffic data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from traffic_updater.transport.rest import router  # noqa: E402
app.include_router(router)

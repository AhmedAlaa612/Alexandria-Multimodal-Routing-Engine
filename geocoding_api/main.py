"""
Geocoding API - FastAPI application entrypoint.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from geocoding_api.config import settings
from geocoding_api.transport.grpc_server import start_grpc_server

_grpc_server = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _grpc_server
    _grpc_server = start_grpc_server()
    print(f"[geocoding] REST listening on port {settings.rest_port}")
    yield
    if _grpc_server:
        _grpc_server.stop(grace=5)
        print("[shutdown] gRPC server stopped")


app = FastAPI(
    title="Geocoding API",
    description="Forward geocoding with Alexandria bias for transit routing",
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

from geocoding_api.transport.rest import router  # noqa: E402
app.include_router(router)

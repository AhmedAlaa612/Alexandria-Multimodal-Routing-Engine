"""
DB Tools API - FastAPI application entrypoint.

Provides database-backed endpoints for GTFS spatial queries.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db_tools.config import settings
from db_tools.db.pool import get_pool
from db_tools.transport.grpc_server import start_grpc_server

_grpc_server = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _grpc_server
    # Warm up the connection pool
    get_pool()
    _grpc_server = start_grpc_server()
    print(f"[db-tools] REST listening on port {settings.rest_port}")
    yield
    if _grpc_server:
        _grpc_server.stop(grace=5)
        print("[shutdown] gRPC server stopped")


app = FastAPI(
    title="DB Tools API",
    description="Database-backed GTFS spatial queries for Alexandria transit",
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

from db_tools.transport.rest import router  # noqa: E402
app.include_router(router)

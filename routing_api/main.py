"""
Routing API — FastAPI application entrypoint.

Loads all network data at startup using the lifespan hook,
then serves REST + gRPC on two ports from a single process.
"""

import warnings
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routing_api.config import settings
from routing_api.network.osm_graph import load_osm_graph
from routing_api.network.trip_graph import load_trip_graph
from routing_api.network.gtfs_lookups import load_gtfs_lookups
from routing_api.network.merge import merge_trips_to_network
from routing_api.cost.distance import load_prefix_distances
from routing_api.cost.fare import load_fare_model
from routing_api.cost.time import load_prefix_times
from routing_api.transport.grpc_server import start_grpc_server

warnings.filterwarnings("ignore")

# ── Shared application state ─────────────────────────────────────────────────
# Populated during startup, read by all request handlers.

app_state: dict = {}
_grpc_server = None


def _load_gtfs_dataframes():
    """Load raw GTFS DataFrames from CSV files."""
    gtfs_path = str(settings.resolve(settings.gtfs_path))
    return {
        "stops": pd.read_csv(f"{gtfs_path}/stops.txt"),
        "routes": pd.read_csv(f"{gtfs_path}/routes.txt"),
        "trips": pd.read_csv(f"{gtfs_path}/trips.txt"),
        "stop_times": pd.read_csv(f"{gtfs_path}/stop_times.txt"),
        "shapes": pd.read_csv(f"{gtfs_path}/shapes.txt"),
    }


def rebuild_all(*, force: bool = False):
    """
    (Re)build all network structures.

    Called once at startup and optionally via admin endpoint.
    """
    global app_state

    print("=" * 60)
    print("[startup] Building routing network...")
    print("=" * 60)

    # 1. OSM graph
    g = load_osm_graph(force_rebuild=force)

    # 2. GTFS raw data
    gtfs = _load_gtfs_dataframes()
    pathways = pd.read_csv(str(settings.resolve(settings.pathways_path)))

    # 3. Trip graph + pathway metadata
    trip_graph, pathway_metadata = load_trip_graph(
        pathways, gtfs["stops"], force_rebuild=force,
    )

    # 4. GTFS lookups
    lookups = load_gtfs_lookups(
        gtfs["stops"], gtfs["routes"], gtfs["trips"], gtfs["shapes"],
        force_rebuild=force,
    )

    # 5. Merge trips to network
    g = merge_trips_to_network(g, gtfs)

    # 6. Cost models
    load_prefix_distances()
    load_fare_model()
    load_prefix_times()

    # 7. Store in shared state
    app_state.update({
        "graph": g,
        "trip_graph": trip_graph,
        "pathway_metadata": pathway_metadata,
        "lookups": lookups,
    })

    print("=" * 60)
    print("[startup] Routing network ready [OK]")
    print("=" * 60)


# ── FastAPI lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load everything. Shutdown: stop gRPC."""
    global _grpc_server
    rebuild_all()
    _grpc_server = start_grpc_server(app_state)
    yield
    if _grpc_server:
        _grpc_server.stop(grace=5)
        print("[shutdown] gRPC server stopped")


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Transit Routing API",
    description="Multi-modal transit routing engine for Alexandria, Egypt",
    version="0.11.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST routes
from routing_api.transport.rest import router  # noqa: E402
app.include_router(router)

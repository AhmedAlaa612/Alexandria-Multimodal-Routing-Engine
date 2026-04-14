"""
REST transport layer — FastAPI router.
"""

from fastapi import APIRouter, HTTPException, Header

from routing_api.schemas.models import JourneyRequest, JourneyResponse, HealthResponse
from routing_api.pipeline import find_journeys
from routing_api.cost.time import reload_prefix_times
from routing_api.config import settings

router = APIRouter(prefix="/api/v1", tags=["routing"])


def _get_app_state():
    """Import here to avoid circular imports — the state is set in main.py."""
    from routing_api.main import app_state
    return app_state


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.post("/journeys", response_model=JourneyResponse)
async def route_journeys(req: JourneyRequest):
    """Find transit journeys between two coordinates."""
    state = _get_app_state()
    try:
        result = find_journeys(
            req.start_lat, req.start_lon,
            req.end_lat, req.end_lon,
            graph=state["graph"],
            trip_graph=state["trip_graph"],
            pathway_metadata=state["pathway_metadata"],
            lookups=state["lookups"],
            max_transfers=req.max_transfers,
            walking_cutoff=req.walking_cutoff,
            weights=req.weights,
            priority=req.priority,
            filters=req.filters,
            top_k=req.top_k,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {e}")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check."""
    state = _get_app_state()
    g = state.get("graph")
    tg = state.get("trip_graph", {})
    lookups = state.get("lookups")
    return HealthResponse(
        status="ok",
        graph_nodes=g.number_of_nodes() if g else 0,
        graph_edges=g.number_of_edges() if g else 0,
        trip_graph_edges=sum(len(v) for v in tg.values()) if tg else 0,
        trips_loaded=len(lookups.trip_to_route) if lookups else 0,
    )


# ── Admin endpoints ──────────────────────────────────────────────────────────

def _check_admin(key: str):
    if key != settings.admin_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@router.post("/admin/reload-times")
async def admin_reload_times(x_admin_key: str = Header(...)):
    """Hot-reload prefixtimes.json from disk."""
    _check_admin(x_admin_key)
    count = reload_prefix_times()
    return {"status": "ok", "trips_reloaded": count}


@router.post("/admin/rebuild")
async def admin_rebuild(x_admin_key: str = Header(...)):
    """Trigger a full network rebuild (expensive, blocks the server)."""
    _check_admin(x_admin_key)
    from routing_api.main import rebuild_all
    rebuild_all(force=True)
    return {"status": "ok", "message": "Full rebuild complete"}
